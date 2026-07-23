import type { StableEvent } from "../../lib/sseClient";

export function EventTimeline({ events }: { events: StableEvent[] }) {
  return (
    <ol className="timeline">
      {events.map((e, i) => (
        <li key={e.event_id ?? `${e.type}-${i}`}>
          <code>{e.type}</code>
          {e.sequence != null ? <span className="muted"> #{e.sequence}</span> : null}
          {e.data ? (
            <pre>{JSON.stringify(e.data, null, 2)}</pre>
          ) : null}
        </li>
      ))}
    </ol>
  );
}
