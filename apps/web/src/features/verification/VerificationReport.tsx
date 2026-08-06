import { mergeAnswer } from "../playground/analysis";
import type { StreamEvent } from "../../lib/sseClient";
import { useI18n } from "../../i18n";
import { BusinessResults } from "./BusinessResults";

type Props = {
  events: StreamEvent[];
  question: string;
  token: string;
};

function flowLabel(event: StreamEvent): string {
  const name = String(event.data?.name ?? "");
  if (event.type === "tool_call") return `tool call: ${name || "unknown"}`;
  if (event.type === "tool_result") return `tool result: ${name || "unknown"}`;
  if (event.type === "step_update") return event.step ? `step: ${event.step}` : event.type;
  return event.type;
}

export function VerificationReport({ events, question, token }: Props) {
  const { t } = useI18n();
  const text = mergeAnswer(events);
  const tools = events.filter((event) => event.type === "tool_call");
  const flow = events.filter((event) => event.type !== "text_delta");
  const hasBusinessDisplay = events.some((event) => event.type.startsWith("x.work_order_ops.") || event.type === "x.bridge.citation");
  const response = text || (hasBusinessDisplay ? t("structuredResultReady") : t("waitingResult"));

  return <section className="verification-report" aria-label={t("verificationReport")}>
    <div className="section-heading"><div><h2>{t("verificationReport")}</h2><p className="muted">{t("scenarioHint")}</p></div></div>
    <div className="verification-facts">
      <section><h3>{t("problem")}</h3><p>{question}</p></section>
      <section><h3>{t("responseResult")}</h3><p aria-live="polite">{response}</p></section>
    </div>
    {events.length ? <>
      <div className="verification-report-grid">
        <section className="report-panel"><h3>{t("calledTools")}</h3>{tools.length ? <ol className="report-tools">{tools.map((event, index) => <li key={event.event_id ?? `${event.type}-${index}`}><code>{String(event.data?.name ?? "unknown")}</code>{event.data?.args ? <small>{JSON.stringify(event.data.args)}</small> : null}</li>)}</ol> : <p className="muted">{t("noToolsCalled")}</p>}</section>
        <section className="report-panel report-flow"><h3>{t("flow")}</h3><ol>{flow.map((event, index) => <li key={event.event_id ?? `${event.type}-${index}`}><code>{flowLabel(event)}</code>{event.status ? <small>{event.status}</small> : null}</li>)}</ol></section>
      </div>
      {hasBusinessDisplay ? <section className="report-display"><h3>{t("structuredDisplay")}</h3><BusinessResults events={events} token={token} onPreset={() => undefined} showPresets={false} showHeading={false} /></section> : null}
    </> : null}
  </section>;
}
