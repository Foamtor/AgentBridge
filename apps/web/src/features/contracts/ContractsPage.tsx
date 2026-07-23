import type { StableEventType } from "../../lib/sseClient";

const TYPES: StableEventType[] = [
  "start",
  "step_update",
  "text_delta",
  "tool_call",
  "tool_result",
  "done",
  "error",
  "cancel_requested",
  "cancelled",
];

export function ContractsPage() {
  return (
    <main className="page">
      <h1>稳定事件类型</h1>
      <p className="lede">与 docs/contracts.md §2 对齐的出站 type 列表。</p>
      <ul className="type-list">
        {TYPES.map((t) => (
          <li key={t}>
            <code>{t}</code>
          </li>
        ))}
      </ul>
    </main>
  );
}
