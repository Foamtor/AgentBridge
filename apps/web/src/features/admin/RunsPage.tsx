import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { adminErrorMessage, adminFetch } from "./adminFetch";

type RunItem = {
  run_id: string;
  thread_id: string;
  route: string;
  status: string;
  started_at?: string;
  ended_at?: string;
};

export function RunsPage() {
  const [items, setItems] = useState<RunItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [route, setRoute] = useState("");

  useEffect(() => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (route) params.set("route", route);
    params.set("limit", "20");
    void adminFetch<{ items: RunItem[] }>(`/admin/runs?${params.toString()}`)
      .then((body) => setItems(body.items))
      .catch((err) => setError(adminErrorMessage(err)));
  }, [status, route]);

  return (
    <main className="page">
      <header>
        <h1>Run 列表</h1>
        <p className="lede">按状态与 route 筛选；点击 run_id 可在调试台查看事件。</p>
      </header>
      <div className="session-bar">
        <label>
          status
          <input value={status} onChange={(e) => setStatus(e.target.value)} placeholder="done" />
        </label>
        <label>
          route
          <input value={route} onChange={(e) => setRoute(e.target.value)} placeholder="echo" />
        </label>
      </div>
      {error ? <p className="error">{error}</p> : null}
      <table className="config-table">
        <thead>
          <tr>
            <th>run_id</th>
            <th>route</th>
            <th>status</th>
            <th>started_at</th>
          </tr>
        </thead>
        <tbody>
          {items.map((run) => (
            <tr key={run.run_id}>
              <td>
                <Link to={`/playground?run_id=${encodeURIComponent(run.run_id)}`}>
                  {run.run_id}
                </Link>
              </td>
              <td>{run.route}</td>
              <td>{run.status}</td>
              <td className="muted">{run.started_at ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!items.length && !error ? <p className="muted">暂无数据</p> : null}
    </main>
  );
}
