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
      status === 401 ? "Unauthorized" : "Forbidden",
    );
  });
});
