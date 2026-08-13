import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { VerificationWorkbench } from "./VerificationWorkbench";

describe("VerificationWorkbench", () => {
  it("shows the verification scenarios and environment state", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/ready")) return Promise.resolve(new Response(JSON.stringify({ status: "ready", checks: { api: { status: "ok" } } }), { status: 200 }));
      return Promise.resolve(new Response(JSON.stringify({ runtime: { llm_backend: "fake" }, context: { tenant_id: "dev" }, reference: { available: true, data_class: "synthetic_redacted" } }), { status: 200 }));
    }));
    render(<MemoryRouter><VerificationWorkbench /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "验证 AgentBridge" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /读取工单/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /生成分布图/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /检索处理规范/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /起草并审批/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /测试自动路由/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByText("验证问题")).toHaveLength(6);
    expect(screen.getByText("当前租户有哪些工单？")).toBeInTheDocument();
    expect(screen.getByText("返回仅属于当前租户的脱敏工单列表，并产生列表结构化事件。")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "验证结果" })).toBeInTheDocument();
    expect(screen.getByText("运行后将在这里显示回复、工具和链路。")).toBeInTheDocument();
    expect(screen.getByText("实时输出（SSE）")).toBeInTheDocument();
    expect(screen.getByText("实时输出（SSE）").closest("details")).toHaveAttribute("open");
    expect(await screen.findByText("就绪")).toBeInTheDocument();
  });

  it("routes a question before executing the selected plugin", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"type":"tool_call","data":{"name":"list_work_orders"}}\n\n'));
        controller.enqueue(encoder.encode('data: {"type":"tool_call","data":{"name":"work_order_statistics"}}\n\n'));
        controller.enqueue(encoder.encode('data: {"type":"x.work_order_ops.list","data":{"rows":[{"id":"WO-1"}]}}\n\n'));
        controller.enqueue(encoder.encode('data: {"type":"x.work_order_ops.chart","data":{"echarts_option":{"series":[{"data":[1]}]}}}\n\n'));
        controller.enqueue(encoder.encode('data: {"type":"done"}\n\n'));
        controller.close();
      },
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/console/route")) return Promise.resolve(new Response(JSON.stringify({
        route: "work_order_ops",
        reason: "Matched keywords: 工单, 状态",
        expected_tools: ["list_work_orders", "work_order_statistics"],
        candidates: [{ route: "work_order_ops", score: 2 }],
      }), { status: 200 }));
      if (url.endsWith("/chat/stream")) {
        expect(JSON.parse(String(init?.body))).toEqual(expect.objectContaining({ route: "work_order_ops" }));
        return Promise.resolve({ ok: true, body: stream } as Response);
      }
      if (url.endsWith("/ready")) return Promise.resolve(new Response(JSON.stringify({ status: "ready", checks: {} }), { status: 200 }));
      if (url.endsWith("/models")) return Promise.resolve(new Response(JSON.stringify({ models: [] }), { status: 200 }));
      return Promise.resolve(new Response(JSON.stringify({ runtime: {}, context: {}, reference: {} }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MemoryRouter><VerificationWorkbench /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: /测试自动路由/ }));
    fireEvent.click(screen.getByRole("button", { name: "运行场景" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/console/route"),
      expect.objectContaining({ method: "POST" }),
    ));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/chat/stream"),
      expect.anything(),
    ));
    expect(await screen.findByText("选中正确业务插件")).toBeInTheDocument();
  });

  it("uses the configured real model alias when running a real scenario", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"type":"done"}\n\n'));
        controller.close();
      },
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/models")) {
        return Promise.resolve(new Response(JSON.stringify({
          models: [{ alias: "production", model_name: "example-model", kind: "real", last_test_status: "success", last_test_capability: "tool_calling_v1" }],
        }), { status: 200 }));
      }
      if (url.endsWith("/chat/stream")) {
        return Promise.resolve({ ok: true, body: stream } as Response);
      }
      if (url.endsWith("/ready")) {
        return Promise.resolve(new Response(JSON.stringify({ status: "ready", checks: {} }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ runtime: { llm_backend: "fake" }, context: {}, reference: {} }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MemoryRouter><VerificationWorkbench /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "真实模型" }));
    fireEvent.click(screen.getByRole("button", { name: "运行场景" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/chat/stream"),
      expect.objectContaining({ body: expect.stringContaining('"model":"production"') }),
    ));
    const streamCall = fetchMock.mock.calls.find(([input]) => String(input).endsWith("/chat/stream"));
    expect(streamCall?.[1]).toEqual(expect.objectContaining({
      body: expect.stringContaining('"case_mode":"real"'),
    }));
  });

  it("requires a successful model connection test before enabling real verification", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/models")) {
        return Promise.resolve(new Response(JSON.stringify({
          models: [{ alias: "unverified", model_name: "example-model", kind: "real", last_test_status: "success", last_test_capability: null }],
        }), { status: 200 }));
      }
      if (url.endsWith("/ready")) return Promise.resolve(new Response(JSON.stringify({ status: "ready", checks: {} }), { status: 200 }));
      return Promise.resolve(new Response(JSON.stringify({ runtime: {}, context: {}, reference: {} }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MemoryRouter><VerificationWorkbench /></MemoryRouter>);

    expect(await screen.findByText(/没有通过“连接与工具调用”测试的真实模型。请先在模型管理中完成测试后再运行。/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "真实模型" })).toBeDisabled();
    expect(screen.getByRole("link", { name: "配置模型" })).toHaveAttribute("href", "/models");
  });

  it("reloads persisted events after approving a draft", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"type":"start","run_id":"r-draft","event_id":"e-1","sequence":1}\n\n'));
        controller.enqueue(encoder.encode('data: {"type":"x.work_order_ops.ledger_preview","run_id":"r-draft","event_id":"e-2","sequence":2,"data":{"title":"Demo draft"}}\n\n'));
        controller.enqueue(encoder.encode('data: {"type":"x.bridge.approval_required","run_id":"r-draft","event_id":"e-3","sequence":3,"data":{"approval_id":"ap-draft"}}\n\n'));
        controller.close();
      },
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/chat/stream")) return Promise.resolve({ ok: true, body: stream } as Response);
      if (url.endsWith("/approvals/ap-draft") && init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ approval: { status: "approved", run_id: "r-draft" } }), { status: 200 }));
      }
      if (url.endsWith("/runs/r-draft/events")) {
        return Promise.resolve(new Response(JSON.stringify([
          { type: "start", run_id: "r-draft", event_id: "e-1", sequence: 1 },
          { type: "x.work_order_ops.ledger_preview", run_id: "r-draft", event_id: "e-2", sequence: 2, data: { title: "Demo draft" } },
          { type: "x.bridge.approval_required", run_id: "r-draft", event_id: "e-3", sequence: 3, data: { approval_id: "ap-draft" } },
          { type: "x.work_order_ops.work_order_created", run_id: "r-draft", event_id: "e-4", sequence: 4, data: { id: "WO-ap-draft" } },
          { type: "done", run_id: "r-draft", event_id: "e-5", sequence: 5 },
        ]), { status: 200 }));
      }
      if (url.endsWith("/ready")) return Promise.resolve(new Response(JSON.stringify({ status: "ready", checks: {} }), { status: 200 }));
      return Promise.resolve(new Response(JSON.stringify({ models: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<MemoryRouter><VerificationWorkbench /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: /起草并审批/ }));
    fireEvent.click(screen.getByRole("button", { name: "运行场景" }));
    fireEvent.click(await screen.findByRole("button", { name: "批准" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/runs/r-draft/events"),
      expect.objectContaining({ credentials: "include" }),
    ));
    expect(screen.getAllByText(/WO-ap-draft/).length).toBeGreaterThan(0);
    expect(screen.getByText("已完成")).toBeInTheDocument();
  });
});
