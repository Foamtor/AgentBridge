import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("console navigation", () => {
  afterEach(() => vi.unstubAllGlobals());

  function token(claims: object): string {
    return `header.${btoa(JSON.stringify(claims))}.signature`;
  }

  it("shows admin navigation for an administrator", () => {
    localStorage.setItem("agentbridge_bearer", token({ roles: ["admin"] }));
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 403 })));
    render(
      <MemoryRouter initialEntries={["/debug"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "调试" })).toHaveAttribute("href", "/debug");
    expect(screen.getByRole("link", { name: "配置" })).toHaveAttribute("href", "/config");
  });

  it("hides admin navigation and redirects a normal user to forbidden", () => {
    localStorage.setItem("agentbridge_bearer", token({ roles: ["viewer"] }));
    render(
      <MemoryRouter initialEntries={["/config"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.queryByRole("link", { name: "配置" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "无权限" })).toBeInTheDocument();
  });
});
