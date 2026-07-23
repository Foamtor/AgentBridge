type Props = {
  query: string;
  busy: boolean;
  onQuery: (v: string) => void;
  onSend: () => void;
  onCancel: () => void;
  onDoubleFire: () => void;
};

export function SendPanel({
  query,
  busy,
  onQuery,
  onSend,
  onCancel,
  onDoubleFire,
}: Props) {
  return (
    <div className="send-panel">
      <textarea
        rows={3}
        value={query}
        onChange={(e) => onQuery(e.target.value)}
        placeholder="输入 query"
      />
      <div className="actions">
        <button type="button" onClick={onSend} disabled={busy || !query.trim()}>
          发送
        </button>
        <button type="button" onClick={onCancel} disabled={!busy}>
          Cancel
        </button>
        <button type="button" onClick={onDoubleFire} disabled={busy}>
          连点测 409
        </button>
      </div>
    </div>
  );
}
