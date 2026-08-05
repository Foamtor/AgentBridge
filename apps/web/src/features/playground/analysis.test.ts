import { describe, expect, it } from "vitest";
import { analyzeEvents, mergeAnswer } from "./analysis";

describe("Playground event analysis", () => {
  it("projects timings, tool duration, and contract assertions from a run", () => {
    const diagnostics = analyzeEvents([
      { type: "start", event_id: "e1", run_id: "r1", trace_id: "t1", sequence: 1, timestamp: 100 },
      { type: "tool_call", event_id: "e2", run_id: "r1", trace_id: "t1", sequence: 2, timestamp: 130, data: { name: "lookup", tool_call_id: "tc1", args: { q: "x" } } },
      { type: "tool_result", event_id: "e3", run_id: "r1", trace_id: "t1", sequence: 3, timestamp: 180, data: { name: "lookup", tool_call_id: "tc1", summary: "ok" } },
      { type: "text_delta", event_id: "e4", run_id: "r1", trace_id: "t1", sequence: 4, timestamp: 200, data: { content: "answer" } },
      { type: "done", event_id: "e5", run_id: "r1", trace_id: "t1", sequence: 5, timestamp: 220 },
    ]);

    expect(diagnostics.contract_ok).toBe(true);
    expect(diagnostics.duration_ms).toBe(120);
    expect(diagnostics.tools[0]).toMatchObject({ name: "lookup", duration_ms: 50 });
    expect(mergeAnswer([{ type: "text_delta", data: { content: "a" } }, { type: "text_delta", data: { text: "b" } }])).toBe("ab");
  });

  it("surfaces duplicate event identifiers as a failed contract", () => {
    const diagnostics = analyzeEvents([
      { type: "start", event_id: "duplicate", run_id: "r1", trace_id: "t1", sequence: 1 },
      { type: "done", event_id: "duplicate", run_id: "r1", trace_id: "t1", sequence: 2 },
    ]);

    expect(diagnostics.contract_ok).toBe(false);
    expect(diagnostics.duplicate_event_ids).toEqual(["duplicate"]);
  });
});
