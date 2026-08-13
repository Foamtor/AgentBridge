import { mergeAnswer } from "../playground/analysis";
import type { StreamEvent } from "../../lib/sseClient";
import { useI18n } from "../../i18n";
import { BusinessResults } from "./BusinessResults";
import type { RouteDecision, VerificationScenario } from "./useVerificationRun";
import { evaluateScenario, type ScenarioCheck } from "./scenarioAssertions";

type Props = {
  events: StreamEvent[];
  question: string;
  token: string;
  scenario?: VerificationScenario;
  onApprovalResolved?: (runId: string) => Promise<void>;
  routeDecision?: RouteDecision | null;
};

function flowLabel(event: StreamEvent): string {
  const name = String(event.data?.name ?? "");
  if (event.type === "tool_call") return `tool call: ${name || "unknown"}`;
  if (event.type === "tool_result") return `tool result: ${name || "unknown"}`;
  if (event.type === "step_update") return event.step ? `step: ${event.step}` : event.type;
  return event.type;
}

function hasDisplayableBusinessResult(event: StreamEvent): boolean {
  if (event.type === "x.bridge.citation") {
    return Array.isArray(event.data?.citations) && event.data.citations.length > 0;
  }
  if (event.type === "x.work_order_ops.list") {
    return Array.isArray(event.data?.rows) && event.data.rows.length > 0;
  }
  if (event.type === "x.work_order_ops.chart") {
    const option = event.data?.echarts_option;
    const series = option && typeof option === "object" && !Array.isArray(option)
      ? (option as { series?: unknown }).series
      : undefined;
    return Array.isArray(series) && series.some((item) => (
      Boolean(item) && typeof item === "object" && Array.isArray((item as { data?: unknown }).data) && (item as { data: unknown[] }).data.length > 0
    ));
  }
  return event.type === "x.work_order_ops.ledger_preview"
    || event.type === "x.work_order_ops.work_order_created"
    || event.type === "x.bridge.approval_required";
}

export function VerificationReport({ events, question, token, scenario = "chart", onApprovalResolved, routeDecision }: Props) {
  const { t } = useI18n();
  const text = mergeAnswer(events);
  const tools = events.filter((event) => event.type === "tool_call");
  const flow = events.filter((event) => event.type !== "text_delta");
  const hasBusinessEvent = events.some((event) => event.type.startsWith("x.work_order_ops.") || event.type === "x.bridge.citation");
  const hasBusinessDisplay = events.some(hasDisplayableBusinessResult);
  const response = text || (hasBusinessDisplay ? t("structuredResultReady") : events.some((event) => ["done", "error", "cancelled"].includes(event.type)) ? t("noBusinessResult") : t("waitingResult"));
  const checks = evaluateScenario(scenario, events, routeDecision);
  const checkLabel = (check: ScenarioCheck) => {
    const labels: Record<ScenarioCheck["id"], "checkList" | "checkChart" | "checkCitation" | "checkDraft" | "checkApproval" | "checkCreatedOnce" | "checkRoute" | "checkRouteTools"> = {
      list: "checkList", chart: "checkChart", citation: "checkCitation", draft: "checkDraft", approval: "checkApproval", created_once: "checkCreatedOnce", route: "checkRoute", route_tools: "checkRouteTools",
    };
    return t(labels[check.id]);
  };
  const statusLabel = (status: ScenarioCheck["status"]) => t(status === "pass" ? "checkPass" : status === "fail" ? "checkFail" : "checkPending");

  return <section className="verification-report" aria-label={t("verificationReport")}>
    <div className="section-heading"><div><h2>{t("verificationReport")}</h2></div></div>
    <div className="verification-facts">
      <section><h3>{t("problem")}</h3><p>{question}</p></section>
      <section><h3>{t("responseResult")}</h3><p aria-live="polite">{response}</p></section>
      {routeDecision ? <section><h3>{t("routeDecision")}</h3><p><strong>{routeDecision.route ?? t("routeNotFound")}</strong><br /><span className="muted">{routeDecision.reason}</span></p></section> : null}
    </div>
    {hasBusinessEvent ? <section className="report-display"><h3>{t("structuredDisplay")}</h3><BusinessResults events={events} token={token} onPreset={() => undefined} onApprovalResolved={onApprovalResolved} showPresets={false} showHeading={false} /></section> : null}
    <section className="report-checks"><h3>{t("expectedChecks")}</h3><ol>{checks.map((check) => <li className={`check-${check.status}`} key={check.id}><div><strong>{checkLabel(check)}</strong><span>{statusLabel(check.status)}</span></div><small>{t("checkEvidence")}: <code>{check.evidenceTypes.join(", ")}</code></small></li>)}</ol></section>
    {events.length ? <>
      <div className="verification-report-grid">
        <section className="report-panel"><h3>{t("calledTools")}</h3>{tools.length ? <ol className="report-tools">{tools.map((event, index) => <li key={event.event_id ?? `${event.type}-${index}`}><code>{String(event.data?.name ?? "unknown")}</code>{event.data?.args ? <small>{JSON.stringify(event.data.args)}</small> : null}</li>)}</ol> : <p className="muted">{t("noToolsCalled")}</p>}</section>
        <section className="report-panel report-flow"><h3>{t("flow")}</h3><ol>{flow.map((event, index) => <li key={event.event_id ?? `${event.type}-${index}`}><code>{flowLabel(event)}</code>{event.status ? <small>{event.status}</small> : null}</li>)}</ol></section>
      </div>
    </> : null}
  </section>;
}
