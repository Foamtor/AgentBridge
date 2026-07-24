import { useState } from "react";
import { isExtensionEvent, type StreamEvent } from "../../lib/sseClient";

export function EventTimeline({ events }: { events: StreamEvent[] }) {
  const [expandExt, setExpandExt] = useState(false);
  const stable = events.filter((e) => !isExtensionEvent(e.type));
  const extensions = events.filter((e) => isExtensionEvent(e.type));

  return (
    <div className="timeline-wrap">
      <ol className="timeline">
        {stable.map((e, i) => (
          <li key={e.event_id ?? `${e.type}-${i}`}>
            <code>{e.type}</code>
            {e.sequence != null ? <span className="muted"> #{e.sequence}</span> : null}
            {e.data ? <pre>{JSON.stringify(e.data, null, 2)}</pre> : null}
          </li>
        ))}
      </ol>
      {extensions.length > 0 ? (
        <details
          className="ext-fold"
          open={expandExt}
          onToggle={(ev) => setExpandExt((ev.target as HTMLDetailsElement).open)}
        >
          <summary>
            扩展事件 x.*（{extensions.length}）— 默认折叠
          </summary>
          <ol className="timeline">
            {extensions.map((e, i) => (
              <li key={e.event_id ?? `ext-${e.type}-${i}`}>
                <code>{e.type}</code>
                {e.sequence != null ? (
                  <span className="muted"> #{e.sequence}</span>
                ) : null}
                {e.data ? <pre>{JSON.stringify(e.data, null, 2)}</pre> : null}
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </div>
  );
}
