type Props = {
  threadId: string;
  route: string;
  token: string;
  onThreadId: (v: string) => void;
  onRoute: (v: string) => void;
  onToken: (v: string) => void;
};

const ROUTES = [
  { value: "echo", label: "echo（最小回声）" },
  { value: "demo_tools", label: "demo_tools（无 LLM / tool + x.*）" },
];

export function SessionBar({
  threadId,
  route,
  token,
  onThreadId,
  onRoute,
  onToken,
}: Props) {
  return (
    <div className="session-bar">
      <label>
        thread_id
        <input value={threadId} onChange={(e) => onThreadId(e.target.value)} />
      </label>
      <label>
        route
        <select value={route} onChange={(e) => onRoute(e.target.value)}>
          {ROUTES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
          {!ROUTES.some((r) => r.value === route) ? (
            <option value={route}>{route}</option>
          ) : null}
        </select>
      </label>
      <label className="grow">
        Bearer（可选）
        <input
          value={token}
          onChange={(e) => onToken(e.target.value)}
          placeholder="粘贴 access token"
        />
      </label>
    </div>
  );
}
