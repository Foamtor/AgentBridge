import { describe, expect, it } from "vitest";
import { evaluateScenario } from "./scenarioAssertions";

describe("evaluateScenario", () => {
  it("does not accept done alone as a successful list verification", () => {
    const checks = evaluateScenario("list", [{ type: "done" }]);

    expect(checks).toEqual([expect.objectContaining({ id: "list", status: "fail" })]);
  });

  it("fails completed scenarios whose business evidence is empty", () => {
    expect(evaluateScenario("list", [
      { type: "x.work_order_ops.list", data: { rows: [] } }, { type: "done" },
    ])[0].status).toBe("fail");
    expect(evaluateScenario("chart", [
      { type: "x.work_order_ops.chart", data: { echarts_option: { series: [{ data: [] }] } } }, { type: "done" },
    ])[0].status).toBe("fail");
    expect(evaluateScenario("knowledge", [
      { type: "x.bridge.citation", data: { citations: [] } }, { type: "done" },
    ])[0].status).toBe("fail");
  });

  it("accepts populated list, chart, and citation evidence", () => {
    expect(evaluateScenario("list", [{ type: "x.work_order_ops.list", data: { rows: [{ id: "WO-1" }] } }])[0].status).toBe("pass");
    expect(evaluateScenario("chart", [{ type: "x.work_order_ops.chart", data: { echarts_option: { series: [{ data: [1] }] } } }])[0].status).toBe("pass");
    expect(evaluateScenario("knowledge", [{ type: "x.bridge.citation", data: { citations: [{ id: "SOP-1" }] } }])[0].status).toBe("pass");
  });

  it("keeps an approval draft pending until it has exactly one creation event", () => {
    const waiting = evaluateScenario("draft", [
      { type: "x.work_order_ops.ledger_preview" },
      { type: "x.bridge.approval_required" },
    ]);
    expect(waiting.map((check) => check.status)).toEqual(["pass", "pass", "pending"]);

    const complete = evaluateScenario("draft", [
      { type: "x.work_order_ops.ledger_preview" },
      { type: "x.bridge.approval_required" },
      { type: "x.work_order_ops.work_order_created" },
      { type: "done" },
    ]);
    expect(complete.map((check) => check.status)).toEqual(["pass", "pass", "pass"]);

    const duplicate = evaluateScenario("draft", [
      { type: "x.work_order_ops.ledger_preview" },
      { type: "x.bridge.approval_required" },
      { type: "x.work_order_ops.work_order_created" },
      { type: "x.work_order_ops.work_order_created" },
      { type: "done" },
    ]);
    expect(duplicate[2].status).toBe("fail");
  });

  it("checks the route decision and the tools actually called", () => {
    const checks = evaluateScenario("routing", [
      { type: "tool_call", data: { name: "list_work_orders" } },
      { type: "tool_call", data: { name: "work_order_statistics" } },
      { type: "done" },
    ], {
      route: "work_order_ops",
      reason: "Matched keywords: 工单, 状态",
      expected_tools: ["list_work_orders", "work_order_statistics"],
      candidates: [],
    });
    expect(checks.map((check) => check.status)).toEqual(["pass", "pass"]);
  });

  it("fails immediately when no plugin matches", () => {
    const checks = evaluateScenario("routing", [], {
      route: null,
      reason: "No plugin routing rule matched the question.",
      expected_tools: [],
      candidates: [],
    });
    expect(checks.map((check) => check.status)).toEqual(["fail", "fail"]);
  });
});
