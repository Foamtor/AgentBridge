import type { PlaygroundCopy } from "./copy";
import type { DiagnosticSummary, RunRecord } from "./types";

type Props = {
  copy: PlaygroundCopy;
  runs: RunRecord[];
  selectedRunId?: string;
  search: string;
  status: string;
  summary: DiagnosticSummary | null;
  onSearch: (value: string) => void;
  onStatus: (value: string) => void;
  onSelect: (run: RunRecord) => void;
  onRefresh: () => void;
};

function shortId(value: string): string {
  return value.length > 17 ? `${value.slice(0, 8)}...${value.slice(-5)}` : value;
}

export function HistoryRail(props: Props) {
  const { copy } = props;
  const needle = props.search.trim().toLowerCase();
  const visible = props.runs.filter((run) => {
    if (props.status && run.status !== props.status) return false;
    if (!needle) return true;
    return [run.run_id, run.thread_id, run.trace_id, run.route]
      .some((value) => value?.toLowerCase().includes(needle));
  });
  const grouped = visible.reduce<Map<string, RunRecord[]>>((result, run) => {
    const group = result.get(run.thread_id) ?? [];
    group.push(run);
    result.set(run.thread_id, group);
    return result;
  }, new Map());

  return <aside className="playground-history" aria-label={copy.history}>
    <div className="rail-heading"><h2>{copy.history}</h2><button type="button" className="icon-command" onClick={props.onRefresh} title={copy.refresh} aria-label={copy.refresh}>↻</button></div>
    <input value={props.search} onChange={(event) => props.onSearch(event.target.value)} placeholder={copy.search} aria-label={copy.search} />
    <select value={props.status} onChange={(event) => props.onStatus(event.target.value)} aria-label={copy.status}>
      <option value="">{copy.filterAll}</option>
      <option value="done">done</option><option value="awaiting_approval">awaiting_approval</option><option value="error">error</option><option value="cancelled">cancelled</option>
    </select>
    <div className="run-groups">
      {[...grouped.entries()].map(([threadId, runs]) => <section className="thread-group" key={threadId}>
        <h3 title={threadId}>{shortId(threadId)}</h3>
        {runs.map((run) => <button type="button" className="run-row" data-selected={props.selectedRunId === run.run_id} key={run.run_id} onClick={() => props.onSelect(run)}>
          <span className={`state-mark state-${run.status}`} aria-hidden="true" />
          <span><strong>{run.route}</strong><small>{shortId(run.run_id)}</small></span>
          <time>{run.started_at ? new Date(run.started_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "--:--"}</time>
        </button>)}
      </section>)}
      {!visible.length ? <p className="rail-empty">{copy.noRuns}</p> : null}
    </div>
    {props.summary ? <section className="diagnostic-summary"><h3>{copy.diagnostics}</h3><dl>
      <div><dt>{copy.totalRuns}</dt><dd>{props.summary.total_runs}</dd></div>
      <div><dt>{copy.contractFailures}</dt><dd>{props.summary.contract_failures}</dd></div>
      <div><dt>{copy.badcases}</dt><dd>{props.summary.badcases}</dd></div>
      <div><dt>{copy.annotations}</dt><dd>{props.summary.annotations}</dd></div>
    </dl></section> : null}
  </aside>;
}
