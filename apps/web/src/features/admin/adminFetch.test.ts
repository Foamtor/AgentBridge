import { afterEach, describe, expect, it, vi } from "vitest";

import { adminFetch } from "./adminFetch";

describe("adminFetch", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends a Bearer header when a local token is present", async () => {
    localStorage.setItem("agentbridge_bearer", "test-token");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await adminFetch<{ items: unknown[] }>("/admin/config");

    expect(fetchMock).toHaveBeenCalledWith(
      "/admin/config",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      }),
    );
  });

  it("does not send Authorization without a token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await adminFetch("/admin/config");

    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined();
  });

  it.each([401, 403])("uses a safe error for HTTP %i", async (status) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: { message: "secret downstream body" } }), {
          status,
        }),
      ),
    );

    await expect(adminFetch("/admin/config")).rejects.toThrow(
      status === 401 ? "登录状态已失效" : "当前账号没有执行此操作的权限",
    );
  });

  it("keeps a stable API error code without exposing downstream details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: { code: "real_model_unavailable", message: "secret" } }), { status: 409 }),
      ),
    );
    await expect(adminFetch("/admin/models/test")).rejects.toMatchObject({
      status: 409,
      code: "real_model_unavailable",
      message: "当前操作与已有配置冲突，请刷新后重试。",
    });
  });

  it("keeps a safe provider failure reason without exposing its body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: { code: "model_connection_test_failed", reason: "connection_http_401", message: "secret" } }), { status: 502 }),
      ),
    );

    await expect(adminFetch("/admin/models/production/test")).rejects.toMatchObject({
      status: 502,
      code: "model_connection_test_failed",
      reason: "connection_http_401",
      message: "Request failed",
    });
  });

  it("keeps the failed validation field without retaining its submitted value", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: [{ loc: ["body", "api_key"], type: "string_too_short", input: "secret" }] }), { status: 422 }),
      ),
    );

    await expect(adminFetch("/admin/models")).rejects.toMatchObject({
      status: 422,
      field: "api_key",
      validationType: "string_too_short",
    });
  });

  it("does not send a reverse-proxy origin error to the forbidden page", async () => {
    const authError = vi.fn();
    window.addEventListener("agentbridge:auth-error", authError);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: { code: "cross_site_request" } }), { status: 403 }),
      ),
    );

    await expect(adminFetch("/admin/models/encryption-key")).rejects.toMatchObject({
      status: 403,
      code: "cross_site_request",
    });
    expect(authError).not.toHaveBeenCalled();
    window.removeEventListener("agentbridge:auth-error", authError);
  });

  it("sends an actual permission denial to the forbidden page", async () => {
    const authError = vi.fn();
    window.addEventListener("agentbridge:auth-error", authError);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: { code: "forbidden" } }), { status: 403 }),
      ),
    );

    await expect(adminFetch("/admin/models/encryption-key")).rejects.toMatchObject({ status: 403 });
    expect(authError).toHaveBeenCalledTimes(1);
    window.removeEventListener("agentbridge:auth-error", authError);
  });

  it("returns English operator messages when locale is requested", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: { code: "real_model_unavailable" } }), { status: 409 }),
      ),
    );

    localStorage.setItem("agentbridge_locale", "en");
    await expect(adminFetch("/admin/models/test")).rejects.toMatchObject({
      message: "This conflicts with the current configuration. Refresh and try again.",
    });
  });
});
