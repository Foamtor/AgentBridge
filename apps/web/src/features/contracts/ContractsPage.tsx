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
      <h1>事件契约</h1>
      <p className="lede">
        与 docs/contracts.md 对齐：稳定九类 + 扩展集{" "}
        <code>x.&lt;domain&gt;.*</code>。
      </p>

      <h2>稳定九类</h2>
      <ul className="type-list">
        {TYPES.map((t) => (
          <li key={t}>
            <code>{t}</code>
          </li>
        ))}
      </ul>

      <h2>扩展事件</h2>
      <p>
        形式：<code>^x\.[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$</code>
        （禁止连续点与尾部点）。样板域 <code>demo_tools</code> 会发出{" "}
        <code>x.demo_tools.finished</code>。调试台默认折叠{" "}
        <code>x.*</code>。
      </p>
      <p className="muted">
        取消为协作式：停消费循环并置位 cancel token，不保证立刻中断正在执行的工具副作用。
      </p>
    </main>
  );
}
