import { useEffect, useState } from "react";
import { adminFetch } from "./adminFetch";

type KnowledgeStatus = {
  backend?: string;
  healthy?: boolean;
  embedding?: Record<string, unknown>;
  ingest_jobs?: unknown[];
};

export function KnowledgePage() {
  const [data, setData] = useState<KnowledgeStatus | null>(null);
  const [blocked, setBlocked] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void adminFetch<KnowledgeStatus>("/admin/knowledge/status")
      .then(setData)
      .catch((err) => {
        const msg = String(err);
        if (msg.includes("blocked_by_base_r_b_status_api") || msg.includes("503")) {
          setBlocked(true);
          return;
        }
        setError(msg);
      });
  }, []);

  return (
    <main className="page">
      <header>
        <h1>知识后端</h1>
        <p className="lede">消费底座 `GET /admin/knowledge/status`；未就绪时显示阻塞提示。</p>
      </header>
      {blocked ? (
        <p className="error">底座能力未就绪（blocked_by_base_r_b_status_api）</p>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
      {data ? (
        <pre>{JSON.stringify(data, null, 2)}</pre>
      ) : !blocked && !error ? (
        <p className="muted">加载中…</p>
      ) : null}
    </main>
  );
}
