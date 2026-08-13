import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { KnowledgePage } from "./KnowledgePage";

describe("KnowledgePage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("ingests console text and refreshes the persisted job list", async () => {
    const fetch = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/ingest")) {
        return Promise.resolve(new Response(JSON.stringify({
          job_id: "ing-123", status: "completed", ingested_count: 1,
        }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({
        backend: "langchain_pg", healthy: true,
        embedding: { status: "ok", model: "bge-m3" },
        ingest_jobs: [{ job_id: "ing-123", status: "completed", ingested_count: 1, updated_at: "2026-08-06T10:00:00Z" }],
      }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetch);
    const user = userEvent.setup();

    render(<KnowledgePage />);

    await screen.findByText("后端已就绪");
    await user.type(screen.getByLabelText("要导入的文本"), "维修流程：先确认现场风险。");
    await user.click(screen.getByRole("button", { name: "导入资料" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/ingest"),
      expect.objectContaining({ method: "POST" }),
    ));
    expect(await screen.findByText("ing-123")).toBeInTheDocument();
    expect(screen.getAllByText("已导入 1 段")).toHaveLength(2);
  });
});
