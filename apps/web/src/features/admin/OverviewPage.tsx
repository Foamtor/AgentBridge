import { useEffect, useState } from "react";
import { adminFetch } from "./adminFetch";

type Overview = {
  domains: { registered: number; graph_ready: number };
  llm_backend: { type: string; status: string };
  knowledge_backend: { type: string; status: string; message?: string };
  infra_ready: { status: string; checks: Record<string, { status: string; reason?: string }> };
  runs_24h: { total: number; errors: number };
  recent_failed_runs: Array<{
    run_id: string;
    route: string;
    status: string;
    started_at?: string;
  }>;
};

export function OverviewPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void adminFetch<Overview>("/admin/overview")
      .then(setData)
      .catch((err) => setError(String(err)));
  }, []);

  return (
    <main className="page">
      <header>
        <h1>总览</h1>
        <p className="lede">近 24 小时运行概况与基础设施状态（不含 Token 用量）。</p>
      </header>
      {error ? <p className="error">{error}</p> : null}
      {!data && !error ? <p className="muted">加载中…</p> : null}
      {data ? (
        <>
          <section className="card-grid">
            <article className="card">
              <h2>业务插件</h2>
              <p>
                已注册 {data.domains.registered}，图就绪 {data.domains.graph_ready}
              </p>
            </article>
            <article className="card">
              <h2>近 24h Run</h2>
              <p>
                总数 {data.runs_24h.total}，错误 {data.runs_24h.errors}
              </p>
            </article>
            <article className="card">
              <h2>LLM 后端</h2>
              <p>
                {data.llm_backend.type} · {data.llm_backend.status}
              </p>
            </article>
            <article className="card">
              <h2>知识后端</h2>
              <p>
                {data.knowledge_backend.type} · {data.knowledge_backend.status}
              </p>
            </article>
            <article className="card">
              <h2>基础设施</h2>
              <p>infra_ready: {data.infra_ready.status}</p>
            </article>
          </section>
          <h2>最近失败 Run</h2>
          {data.recent_failed_runs.length === 0 ? (
            <p className="muted">暂无失败记录</p>
          ) : (
            <ul className="timeline">
              {data.recent_failed_runs.map((run) => (
                <li key={run.run_id}>
                  <strong>{run.run_id}</strong> · {run.route} · {run.status}
                  {run.started_at ? <span className="muted"> · {run.started_at}</span> : null}
                </li>
              ))}
            </ul>
          )}
        </>
      ) : null}
    </main>
  );
}
