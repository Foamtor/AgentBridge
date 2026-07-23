type Props = {
  threadId: string;
  route: string;
  token: string;
  onThreadId: (v: string) => void;
  onRoute: (v: string) => void;
  onToken: (v: string) => void;
};

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
        <input value={route} onChange={(e) => onRoute(e.target.value)} />
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
