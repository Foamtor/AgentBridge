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
    expect(screen.getByRole("button", { name: /读取工单/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /生成分布图/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /检索处理规范/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /起草并审批/ })).toBeInTheDocument();
    expect(await screen.findByText("就绪")).toBeInTheDocument();
  });
});
