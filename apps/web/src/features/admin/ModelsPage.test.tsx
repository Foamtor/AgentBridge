import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ModelsPage } from "./ModelsPage";

describe("ModelsPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("generates a visible Fernet key before saving it", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ models: [], encryption_ready: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ configured: true, runtime_ready: true, restart_required: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    const user = userEvent.setup();

    render(<ModelsPage />);

    await screen.findByText("尚未配置模型凭据加密密钥");
    await user.click(screen.getByRole("button", { name: "生成随机密钥" }));
    const keyInput = screen.getByLabelText("加密密钥（可粘贴或生成）");
    expect((keyInput as HTMLInputElement).value).toMatch(/^[A-Za-z0-9_-]{43}=$/);
    await user.type(screen.getByLabelText("确认当前密码"), "Password2026");
    await user.click(screen.getByRole("button", { name: "保存加密密钥" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    expect(fetch.mock.calls[1][0]).toContain("/admin/models/encryption-key");
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toMatchObject({ current_password: "Password2026" });
    expect(JSON.parse(fetch.mock.calls[1][1].body).encryption_key).toMatch(/^[A-Za-z0-9_-]{43}=$/);
    expect(screen.getByText("加密密钥已保存并在当前 API 生效。请备份密钥，并在方便时重启 API。")).toBeInTheDocument();
  });

  it("runs a connection test and shows its persisted result", async () => {
    const model = {
      alias: "production", api_base: "https://models.example.test/v1", model_name: "example-model",
      temperature: 0, enabled: true, key_configured: true, runtime_ready: true,
    };
    const fetch = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/admin/models/production/test")) {
        return Promise.resolve(new Response(JSON.stringify({ ok: true, latency_ms: 18, model_name: "example-model" }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({
        models: [{ ...model, last_test_status: "success", last_test_capability: "tool_calling_v1", last_test_latency_ms: 18, last_tested_at: "2026-08-06T10:00:00Z" }],
        encryption_ready: true,
      }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetch);
    const user = userEvent.setup();

    render(<ModelsPage />);
    await user.click(await screen.findByRole("button", { name: "测试连接与工具调用" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/admin/models/production/test"),
      expect.objectContaining({ method: "POST" }),
    ));
    expect(await screen.findByText(/已加载 · 连接和工具调用已通过（18 ms）/)).toBeInTheDocument();
  });

  it("explains when a model passes basic chat but fails tool calling", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      models: [{
        alias: "plain-chat", api_base: "https://models.example.test/v1", model_name: "example-model",
        temperature: 0, enabled: true, key_configured: true, runtime_ready: true,
        last_test_status: "failed", last_test_error: "tool_call_response_missing",
      }],
      encryption_ready: true,
    }), { status: 200 })));

    render(<ModelsPage />);

    expect(await screen.findByText(/已加载 · 工具调用测试未通过/)).toBeInTheDocument();
    expect(screen.getByText(/模型服务拒绝了工具调用测试请求，或没有返回工具调用。/)).toBeInTheDocument();
  });

  it("shows a safe field-level message for rejected model input", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ models: [], encryption_ready: true }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        detail: [{ loc: ["body", "api_key"], type: "string_too_short", input: "secret" }],
      }), { status: 422 }));
    vi.stubGlobal("fetch", fetch);
    const user = userEvent.setup();

    render(<ModelsPage />);
    await screen.findByRole("heading", { name: "添加模型" });
    await user.type(screen.getByLabelText("别名"), "深度求索 V4.1 Flash");
    await user.clear(screen.getByLabelText("API 地址"));
    await user.type(screen.getByLabelText("API 地址"), "https://api.deepseek.com/v1");
    await user.type(screen.getByLabelText("模型名称"), "deepseek-chat");
    await user.type(screen.getByLabelText("API Key"), "placeholder");
    await user.click(screen.getByRole("button", { name: "添加模型" }));

    expect(await screen.findByText("API Key 不能为空。")).toBeInTheDocument();
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });

  it("submits a readable model alias without applying an identifier convention", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ models: [], encryption_ready: true }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ alias: "DeepSeek V4 Flash" }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ models: [], encryption_ready: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    const user = userEvent.setup();

    render(<ModelsPage />);
    await screen.findByRole("heading", { name: "添加模型" });
    await user.type(screen.getByLabelText("别名"), "DeepSeek V4 Flash");
    await user.clear(screen.getByLabelText("API 地址"));
    await user.type(screen.getByLabelText("API 地址"), "https://api.deepseek.com/v1");
    await user.type(screen.getByLabelText("模型名称"), "deepseek-chat");
    await user.type(screen.getByLabelText("API Key"), "placeholder");
    await user.click(screen.getByRole("button", { name: "添加模型" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
    expect(fetch.mock.calls[1][1]).toMatchObject({
      headers: { "Content-Type": "application/json" },
    });
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toMatchObject({
      alias: "DeepSeek V4 Flash",
    });
  });
});
