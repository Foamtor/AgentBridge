import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OverviewPage } from "./OverviewPage";

describe("Admin center", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("groups management tasks and sends failed runs to the playground", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      domains: { registered: 8, graph_ready: 8 },
      llm_backend: { type: "direct", status: "ok" },
      knowledge_backend: { type: "fake", status: "skipped" },
      infra_ready: { status: "ready", checks: {} },
      runs_24h: { total: 16, errors: 1 },
      recent_failed_runs: [{ run_id: "r-failed", route: "work_order_ops", status: "error" }],
    }), { status: 200 })));

    render(<MemoryRouter><OverviewPage /></MemoryRouter>);

    expect(await screen.findByRole("heading", { name: "管理中心" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "先配置，才能进行真实验证" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /模型连接/ })[0]).toHaveAttribute("href", "/models");
    expect(screen.getByRole("link", { name: /工具与权限/ })).toHaveAttribute("href", "/tools");
    expect(screen.getByRole("link", { name: "查看运行记录 ->" })).toHaveAttribute("href", "/runs");
    expect(screen.getByRole("link", { name: "r-failed" })).toHaveAttribute("href", "/playground?run_id=r-failed");
  });
});
