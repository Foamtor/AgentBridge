import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConfigPage } from "./ConfigPage";

describe("ConfigPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("edits safe runtime settings with the current password and keeps secrets read-only", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [
        { key: "RATE_LIMIT_PER_MINUTE", value: 20, tier: "A", description: "每分钟限流", writable: true, source: "database" },
        { key: "EMBED_API_KEY", value: null, tier: "C", description: "Embedding API Key", configured: true },
      ] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ key: "RATE_LIMIT_PER_MINUTE", value: 42, tier: "A", source: "database" }), { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    const user = userEvent.setup();
    render(<ConfigPage />);

    await screen.findByRole("heading", { name: "平台配置" });
    await user.clear(screen.getByRole("spinbutton", { name: "RATE_LIMIT_PER_MINUTE" }));
    await user.type(screen.getByRole("spinbutton", { name: "RATE_LIMIT_PER_MINUTE" }), "42");
    await user.type(screen.getByLabelText("确认当前密码"), "Password2026");
    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    expect(fetch.mock.calls[1][0]).toContain("/admin/config/RATE_LIMIT_PER_MINUTE");
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ value: 42, current_password: "Password2026" });
    expect(screen.getByText("已配置")).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "EMBED_API_KEY" })).not.toBeInTheDocument();
  });
});
