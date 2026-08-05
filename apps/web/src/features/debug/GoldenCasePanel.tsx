import { useEffect, useRef, useState } from "react";
import { BarChart, LineChart, PieChart } from "echarts/charts";
import { GridComponent, LegendComponent, TitleComponent, TooltipComponent } from "echarts/components";
import { init, use, type EChartsCoreOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { apiBase } from "../../lib/apiBase";
import type { StreamEvent } from "../../lib/sseClient";
import { useI18n } from "../../i18n";

type Props = {
  events: StreamEvent[];
  token: string;
  onPreset: (preset: "list" | "chart" | "draft") => void;
  showPresets?: boolean;
};

use([BarChart, LineChart, PieChart, GridComponent, LegendComponent, TitleComponent, TooltipComponent, CanvasRenderer]);

function eventData(events: StreamEvent[], type: string): Record<string, unknown> | undefined {
  return [...events].reverse().find((event) => event.type === type)?.data;
}

function asRows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === "object")
    : [];
}

function Chart({ option }: { option: unknown }) {
  const node = useRef<HTMLDivElement | null>(null);
  const [invalid, setInvalid] = useState(false);

  useEffect(() => {
    if (!node.current || !option || typeof option !== "object" || Array.isArray(option)) {
      setInvalid(true);
      return;
    }
    const chart = init(node.current);
    try {
      // The API emits JSON data. The UI never evaluates scripts or callbacks from it.
      chart.setOption(option as EChartsCoreOption, { notMerge: true });
      setInvalid(false);
    } catch {
      setInvalid(true);
    }
    return () => chart.dispose();
  }, [option]);

  if (invalid) return <p className="muted">Chart data is unavailable; inspect the JSON timeline below.</p>;
  return <div className="golden-chart" ref={node} aria-label="Work-order chart" />;
}

export function GoldenCasePanel({ events, token, onPreset, showPresets = true }: Props) {
  const { t } = useI18n();
  const list = eventData(events, "x.work_order_ops.list");
  const chart = eventData(events, "x.work_order_ops.chart");
  const citation = eventData(events, "x.bridge.citation");
  const draft = eventData(events, "x.work_order_ops.ledger_preview");
  const approval = eventData(events, "x.bridge.approval_required");
  const created = eventData(events, "x.work_order_ops.work_order_created");
  const [approvalState, setApprovalState] = useState<string | null>(null);

  const approvalId = typeof approval?.approval_id === "string" ? approval.approval_id : "";
  const columns = asRows(list?.columns);
  const rows = asRows(list?.rows);
  const citations = asRows(citation?.citations);

  async function decide(decision: "approve" | "deny") {
    if (!approvalId) return;
    setApprovalState(t("submitApproval"));
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token.trim()) headers.Authorization = `Bearer ${token.trim()}`;
    try {
      const response = await fetch(`${apiBase()}/approvals/${encodeURIComponent(approvalId)}`, {
        method: "POST",
        headers,
        body: JSON.stringify({ decision }),
      });
      const body = (await response.json()) as { approval?: { status?: string; result?: unknown } };
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setApprovalState(`${t("approvalStatus")}：${body.approval?.status ?? decision}`);
    } catch (error) {
      setApprovalState(`${t("approvalFailed")}：${String(error)}`);
    }
  }

  return (
    <section className="golden-case" aria-label="Work-order golden case">
      <div className="golden-heading">
        <div>
          <h2>{t("workOrderCase")}</h2>
          <p className="muted">{t("workOrderCaseDescription")}</p>
        </div>
        {showPresets ? <div className="actions">
          <button type="button" onClick={() => onPreset("list")}>{t("list")}</button>
          <button type="button" onClick={() => onPreset("chart")}>{t("chart")}</button>
          <button type="button" onClick={() => onPreset("draft")}>{t("draft")}</button>
        </div> : null}
      </div>

      {rows.length ? (
        <div className="golden-card">
          <h3>{t("workOrders")}</h3>
          <div className="table-scroll"><table><thead><tr>{columns.map((column) => {
            const key = String(column.key ?? "");
            return <th key={key}>{String(column.label ?? key)}</th>;
          })}</tr></thead><tbody>{rows.map((row, index) => <tr key={String(row.id ?? index)}>{columns.map((column) => {
            const key = String(column.key ?? "");
            return <td key={key}>{String(row[key] ?? "—")}</td>;
          })}</tr>)}</tbody></table></div>
        </div>
      ) : null}

      {chart ? <div className="golden-card"><h3>{t("statistics")}</h3><Chart option={chart.echarts_option} /></div> : null}

      {citations.length ? <div className="golden-card"><h3>{t("citations")}</h3><ul>{citations.map((hit, index) => <li key={String(hit.id ?? index)}>{String(hit.title ?? hit.source ?? t("citations"))}</li>)}</ul></div> : null}

      {draft ? <div className="golden-card"><h3>{t("ledgerPreview")}</h3><pre>{JSON.stringify(draft, null, 2)}</pre></div> : null}

      {approval ? <div className="golden-card approval-card"><h3>{t("approvalRequired")}</h3><p>{t("approvalStatus")}：<code>{approvalId || t("approvalPending")}</code></p><div className="actions"><button type="button" disabled={!approvalId} onClick={() => void decide("approve")}>{t("approve")}</button><button type="button" className="secondary" disabled={!approvalId} onClick={() => void decide("deny")}>{t("deny")}</button></div>{approvalState ? <p className="muted">{approvalState}</p> : null}</div> : null}

      {created ? <div className="golden-card success-card"><h3>{t("created")}</h3><pre>{JSON.stringify(created, null, 2)}</pre></div> : null}
    </section>
  );
}
