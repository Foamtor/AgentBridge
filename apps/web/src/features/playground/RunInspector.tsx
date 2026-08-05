import { useState } from "react";
import type { StreamEvent } from "../../lib/sseClient";
import { formatDuration } from "./analysis";
import type { PlaygroundCopy } from "./copy";
import type { InspectorTab, RunAnnotation, RunDiagnostics, RunRecord } from "./types";

type Props = {
  copy: PlaygroundCopy;
  run: RunRecord | null;
  events: StreamEvent[];
  diagnostics: RunDiagnostics | null;
  annotations: RunAnnotation[];
  onCreateAnnotation: (body: { category: string; rating: string; reason: string; expected_behavior: string; tags: string[] }) => Promise<void>;
  onDeleteAnnotation: (id: string) => Promise<void>;
  onExportEvents: () => Promise<void>;
};

export function RunInspector(props: Props) {
  const { copy, run, diagnostics } = props;
  const [tab, setTab] = useState<InspectorTab>("overview");
  const [category, setCategory] = useState("note");
  const [reason, setReason] = useState("");
  const [expected, setExpected] = useState("");
  const [tags, setTags] = useState("");
  const tabs: Array<[InspectorTab, string]> = [["overview", copy.overview], ["timing", copy.timing], ["tools", copy.tools], ["contract", copy.contract], ["raw", copy.raw], ["notes", copy.notes]];

  async function save() {
    if (!reason.trim()) return;
    await props.onCreateAnnotation({ category, rating: category === "badcase" ? "negative" : "neutral", reason: reason.trim(), expected_behavior: expected.trim(), tags: tags.split(",").map((item) => item.trim()).filter(Boolean) });
    setReason(""); setExpected(""); setTags("");
  }

  return <aside className="run-inspector">
    <div className="inspector-heading"><h2>{copy.inspector}</h2>{run ? <span className={`status-pill status-${run.status}`}>{run.status}</span> : null}</div>
    <div className="inspector-tabs" role="tablist">{tabs.map(([key, label]) => <button type="button" role="tab" aria-selected={tab === key} key={key} onClick={() => setTab(key)}>{label}</button>)}</div>
    {!run || !diagnostics ? <p className="inspector-empty">{copy.noSelection}</p> : <div className="inspector-body">
      {tab === "overview" ? <Overview copy={copy} run={run} diagnostics={diagnostics} /> : null}
      {tab === "timing" ? <Timing copy={copy} diagnostics={diagnostics} /> : null}
      {tab === "tools" ? <Tools copy={copy} diagnostics={diagnostics} /> : null}
      {tab === "contract" ? <Contract copy={copy} diagnostics={diagnostics} /> : null}
      {tab === "raw" ? <Raw copy={copy} events={props.events} onExport={props.onExportEvents} /> : null}
      {tab === "notes" ? <div className="annotation-panel">
        <div className="annotation-form"><label><span>{copy.category}</span><select value={category} onChange={(event) => setCategory(event.target.value)}><option value="note">{copy.note}</option><option value="badcase">{copy.badcase}</option></select></label><label><span>{copy.reason}</span><textarea rows={3} value={reason} onChange={(event) => setReason(event.target.value)} /></label><label><span>{copy.expected}</span><textarea rows={2} value={expected} onChange={(event) => setExpected(event.target.value)} /></label><label><span>{copy.tags}</span><input value={tags} onChange={(event) => setTags(event.target.value)} /></label><button type="button" onClick={() => void save()} disabled={!reason.trim()}>{copy.addNote}</button></div>
        <ol className="annotation-list">{props.annotations.map((item) => <li key={item.annotation_id}><div><strong>{item.category}</strong><time>{new Date(item.created_at).toLocaleString()}</time></div><p>{item.reason}</p>{item.expected_behavior ? <small>{item.expected_behavior}</small> : null}<button type="button" className="text-command" onClick={() => void props.onDeleteAnnotation(item.annotation_id)}>{copy.delete}</button></li>)}</ol>
      </div> : null}
    </div>}
  </aside>;
}

function Overview({ copy, run, diagnostics }: { copy: PlaygroundCopy; run: RunRecord; diagnostics: RunDiagnostics }) {
  return <dl className="run-facts"><div><dt>{copy.run}</dt><dd title={run.run_id}>{run.run_id}</dd></div><div><dt>{copy.trace}</dt><dd title={diagnostics.trace_id}>{diagnostics.trace_id ?? "-"}</dd></div><div><dt>{copy.status}</dt><dd>{diagnostics.terminal ?? run.status}</dd></div><div><dt>{copy.duration}</dt><dd>{formatDuration(diagnostics.duration_ms)}</dd></div><div><dt>{copy.events}</dt><dd>{diagnostics.event_count}</dd></div><div><dt>{copy.contract}</dt><dd className={diagnostics.contract_ok ? "check-pass" : "check-fail"}>{diagnostics.contract_ok ? copy.passed : copy.failed}</dd></div></dl>;
}

function Timing({ copy, diagnostics }: { copy: PlaygroundCopy; diagnostics: RunDiagnostics }) {
  const maximum = Math.max(...diagnostics.milestones.map((item) => item.offset_ms ?? 0), 1);
  return <ol className="timing-list">{diagnostics.milestones.map((item, index) => <li key={`${item.sequence ?? index}-${item.type}`}><div><code>{item.type}</code><span>{formatDuration(item.offset_ms)}</span></div><div className="timing-track"><i style={{ width: `${Math.max(2, ((item.offset_ms ?? 0) / maximum) * 100)}%` }} /></div><small>{item.step ?? "-"} · {copy.gap} {formatDuration(item.gap_ms)}</small></li>)}</ol>;
}

function Tools({ copy, diagnostics }: { copy: PlaygroundCopy; diagnostics: RunDiagnostics }) {
  if (!diagnostics.tools.length) return <p className="inspector-empty">{copy.noTools}</p>;
  return <ol className="tool-traces">{diagnostics.tools.map((tool) => <li key={tool.tool_call_id}><div><strong>{tool.name ?? "unknown"}</strong><span>{formatDuration(tool.duration_ms)}</span></div><code>{tool.tool_call_id}</code><details><summary>args</summary><pre>{JSON.stringify(tool.args, null, 2)}</pre></details><details><summary>result</summary><pre>{JSON.stringify(tool.result, null, 2)}</pre></details></li>)}</ol>;
}

function Contract({ copy, diagnostics }: { copy: PlaygroundCopy; diagnostics: RunDiagnostics }) {
  return <ul className="contract-checks">{diagnostics.assertions.map((item) => <li key={item.key} data-pass={item.passed}><span aria-hidden="true">{item.passed ? "✓" : "×"}</span><div><strong>{item.key}</strong><small>{item.detail}</small></div><em>{item.passed ? copy.passed : copy.failed}</em></li>)}</ul>;
}

function Raw({ copy, events, onExport }: { copy: PlaygroundCopy; events: StreamEvent[]; onExport: () => Promise<void> }) {
  return <div className="raw-events"><button type="button" className="download-command" onClick={() => void onExport()}>{copy.export}</button>{events.length ? events.map((event, index) => <details key={event.event_id ?? index}><summary><code>#{event.sequence ?? "-"} {event.type}</code></summary><pre>{JSON.stringify(event, null, 2)}</pre></details>) : <p>{copy.noEvents}</p>}</div>;
}
