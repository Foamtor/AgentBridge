import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DomainsPage } from "./DomainsPage";

describe("Loaded business capabilities", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("explains plugins without tools and shows per-tool approval requirements", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      domains: [
        { name: "demo_approval_write", description: "Approval demo", tools: [], tool_details: [], approval_actions: [], graph_registered: true },
        {
          name: "work_order_ops", description: "Work order reference", tools: ["prepare_work_order_draft"], graph_registered: true,
          tool_details: [{ name: "prepare_work_order_draft", description: "Prepare a draft", required_roles: [], required_permissions: [], required_permissions_all: ["workorder:create", "workorder:assign"] }],
          approval_actions: [{ type: "work_order_ops.create_v1", resource: { name: "create_work_order", required_permissions_all: ["workorder:create", "workorder:assign"] } }],
        },
      ],
    }), { status: 200 })));

    render(<MemoryRouter><DomainsPage /></MemoryRouter>);

    expect(await screen.findByRole("heading", { name: "已加载插件" })).toBeInTheDocument();
    expect(screen.getByText("这个插件没有公开给模型的工具；它通过自身流程图完成处理，并非缺少配置。")).toBeInTheDocument();
    expect(screen.getAllByText("必须同时具备：workorder:create、workorder:assign")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "进入插件调试 ->" })).toHaveAttribute("href", "/playground");
    expect(screen.getAllByRole("link", { name: "查看工具权限" })[0]).toHaveAttribute("href", "/tools?route=demo_approval_write");
  });
});
