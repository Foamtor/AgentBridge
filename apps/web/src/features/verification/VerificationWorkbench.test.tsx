import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { VerificationWorkbench } from "./VerificationWorkbench";

describe("VerificationWorkbench", () => {
  it("shows the four verification scenarios and environment state", async () => {
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
    expect(screen.getAllByText("验证问题")).toHaveLength(5);
    expect(screen.getByText("当前租户有哪些工单？")).toBeInTheDocument();
    expect(screen.getByText("返回仅属于当前租户的脱敏工单列表，并产生列表结构化事件。")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "验证结果" })).toBeInTheDocument();
    expect(screen.getByText("运行后将在这里显示回复、工具和链路。")).toBeInTheDocument();
    expect(await screen.findByText("就绪")).toBeInTheDocument();
  });
});
