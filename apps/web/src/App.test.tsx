import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("console navigation", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows verification and administration navigation for a local administrator", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      status: "authenticated", username: "admin", permissions: ["*"],
    }), { status: 200 })));
    render(<MemoryRouter initialEntries={["/"]}><App /></MemoryRouter>);

    expect(await screen.findByRole("link", { name: "验证工作台" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "配置" })).toHaveAttribute("href", "/config");
  });

  it("redirects an anonymous visitor to the local login page", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "anonymous" }), { status: 200 })));
    render(<MemoryRouter initialEntries={["/config"]}><App /></MemoryRouter>);

    expect(await screen.findByRole("heading", { name: "登录控制台" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "配置" })).not.toBeInTheDocument();
  });

  it("reports reverse-proxy origin failures separately from invalid credentials", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "anonymous" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        detail: { code: "cross_site_request" },
      }), { status: 403 })));
    render(<MemoryRouter initialEntries={["/login"]}><App /></MemoryRouter>);

    fireEvent.change(await screen.findByLabelText("一次性初始密码"), {
      target: { value: "initial-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "继续" }));

    expect(await screen.findByText("登录请求未通过同源校验，请检查 Web 反向代理配置。")).toBeInTheDocument();
  });
});
