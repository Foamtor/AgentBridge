import type { StreamEvent } from "../../lib/sseClient";
import type { VerificationScenario } from "./useVerificationRun";

export type ScenarioCheckStatus = "pass" | "fail" | "pending";

export type ScenarioCheck = {
  id: "list" | "chart" | "citation" | "draft" | "approval" | "created_once";
  status: ScenarioCheckStatus;
  evidenceTypes: string[];
};

function isTerminal(events: StreamEvent[]): boolean {
  return events.some((event) => ["done", "error", "cancelled"].includes(event.type));
}

function requiredCheck(
  id: ScenarioCheck["id"],
  events: StreamEvent[],
  evidenceTypes: string[],
  predicate: (event: StreamEvent) => boolean = () => true,
): ScenarioCheck {
  const passed = events.some((event) => evidenceTypes.includes(event.type) && predicate(event));
  return { id, status: passed ? "pass" : isTerminal(events) ? "fail" : "pending", evidenceTypes };
}

function hasRows(event: StreamEvent): boolean {
  return Array.isArray(event.data?.rows) && event.data.rows.length > 0;
}

function hasChartSeries(event: StreamEvent): boolean {
  const option = event.data?.echarts_option;
  const series = option && typeof option === "object" && !Array.isArray(option)
    ? (option as { series?: unknown }).series
    : undefined;
  return Array.isArray(series) && series.some((item) => (
    Boolean(item) && typeof item === "object" && Array.isArray((item as { data?: unknown }).data) && (item as { data: unknown[] }).data.length > 0
  ));
}

function hasCitations(event: StreamEvent): boolean {
  return Array.isArray(event.data?.citations) && event.data.citations.length > 0;
}

export function evaluateScenario(scenario: VerificationScenario, events: StreamEvent[]): ScenarioCheck[] {
  if (scenario === "list") {
    return [requiredCheck("list", events, ["x.work_order_ops.list"], hasRows)];
  }
  if (scenario === "chart") {
    return [requiredCheck(
      "chart",
      events,
      ["x.work_order_ops.chart"],
      hasChartSeries,
    )];
  }
  if (scenario === "knowledge") {
    return [requiredCheck("citation", events, ["x.bridge.citation"], hasCitations)];
  }

  const created = events.filter((event) => event.type === "x.work_order_ops.work_order_created");
  return [
    requiredCheck("draft", events, ["x.work_order_ops.ledger_preview"]),
    requiredCheck("approval", events, ["x.bridge.approval_required"]),
    {
      id: "created_once",
      status: created.length === 1 ? "pass" : created.length > 1 || isTerminal(events) ? "fail" : "pending",
      evidenceTypes: ["x.work_order_ops.work_order_created"],
    },
  ];
}
