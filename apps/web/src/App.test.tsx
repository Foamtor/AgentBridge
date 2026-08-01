import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("console navigation", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("keeps the debugging and admin entry points available", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 403 })));
    render(
      <MemoryRouter initialEntries={["/debug"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "调试" })).toHaveAttribute("href", "/debug");
    expect(screen.getByRole("link", { name: "配置" })).toHaveAttribute("href", "/config");
  });
});
