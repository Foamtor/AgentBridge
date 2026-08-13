import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { adminErrorMessage, adminFetch } from "./adminFetch";
import { useI18n } from "../../i18n";

type RunItem = {
  run_id: string;
  thread_id: string;
  route: string;
  trace_id?: string;
  status: string;
  started_at?: string;
  ended_at?: string;
  tool_count?: number;
  approval_status?: string | null;
  error?: { code?: string; message?: string } | null;
};

export function RunsPage() {
  const { locale } = useI18n();
  const copy = locale === "en" ? {
    title: "Run records", intro: "Review completed and failed plugin runs after a test. Open a run to inspect its response, tools, approvals, and event timeline.", status: "Status", route: "Plugin", since: "From", until: "To", all: "All", loading: "Loading…", empty: "No runs match these filters.", run: "Run", thread: "Thread", trace: "Trace", started: "Started", ended: "Ended", details: "Details", tools: "tools", approval: "approval", pending: "Pending", errorReason: "Failure", open: "Open in debugging", error: "Could not load run records.", statusOptions: { done: "Completed", error: "Failed", cancelled: "Cancelled", running: "Running", awaiting_approval: "Waiting for approval", waiting_approval: "Waiting for approval" } as Record<string, string>,
  } : {
    title: "运行记录", intro: "查看插件测试完成或失败后的运行结果。列表直接显示工具数量、审批状态和失败原因，打开记录可检查完整时间线。", status: "状态", route: "插件", since: "开始时间", until: "结束时间", all: "全部", loading: "正在读取运行记录…", empty: "没有符合筛选条件的运行记录。", run: "运行", thread: "会话", trace: "链路", started: "开始时间", ended: "结束时间", details: "本次详情", tools: "个工具", approval: "审批", pending: "等待中", errorReason: "失败原因", open: "在插件调试中打开", error: "无法读取运行记录。", statusOptions: { done: "已完成", error: "失败", cancelled: "已取消", running: "运行中", awaiting_approval: "等待审批", waiting_approval: "等待审批" } as Record<string, string>,
  };
  const [items, setItems] = useState<RunItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [route, setRoute] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");

  useEffect(() => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (route) params.set("route", route);
    if (since) params.set("since", new Date(`${since}T00:00:00`).toISOString());
    if (until) params.set("until", new Date(`${until}T23:59:59`).toISOString());
    params.set("limit", "20");
    void adminFetch<{ items: RunItem[] }>(`/admin/runs?${params.toString()}`)
      .then((body) => setItems(body.items))
      .catch((err) => setError(adminErrorMessage(err, locale)));
  }, [status, route, since, until, locale]);

  return (
    <main className="page admin-subpage runs-page">
      <header className="admin-page-header">
        <h1>{copy.title}</h1>
        <p className="lede">{copy.intro}</p>
      </header>
      <div className="session-bar">
        <label>
          {copy.status}
          <select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">{copy.all}</option>{Object.entries(copy.statusOptions).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        </label>
        <label>
          {copy.route}
          <input value={route} onChange={(e) => setRoute(e.target.value)} placeholder="work_order_ops" />
        </label>
        <label>{copy.since}<input type="date" value={since} onChange={(e) => setSince(e.target.value)} /></label>
        <label>{copy.until}<input type="date" value={until} onChange={(e) => setUntil(e.target.value)} /></label>
      </div>
      {error ? <p className="error">{error}</p> : null}
      <table className="config-table">
        <thead>
          <tr>
            <th>{copy.run}</th><th>{copy.route}</th><th>{copy.status}</th><th>{copy.details}</th><th>{copy.thread}</th><th>{copy.trace}</th><th>{copy.started}</th><th>{copy.ended}</th><th />
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
              <td>{run.route}</td><td>{copy.statusOptions[run.status] ?? run.status}</td><td className="run-details"><span>{run.tool_count ?? 0} {copy.tools}</span>{run.approval_status ? <span>{copy.approval}: {run.approval_status === "pending" ? copy.pending : run.approval_status}</span> : null}{run.error?.message ? <small title={run.error.code}>{copy.errorReason}: {run.error.message}</small> : null}</td><td><code>{run.thread_id || "-"}</code></td><td><code>{run.trace_id || "-"}</code></td><td className="muted">{run.started_at ?? "-"}</td><td className="muted">{run.ended_at ?? "-"}</td><td><Link to={`/playground?run_id=${encodeURIComponent(run.run_id)}`}>{copy.open}</Link></td>
            </tr>
          ))}
        </tbody>
      </table>
      {!items.length && !error ? <p className="muted">{copy.empty}</p> : null}
    </main>
  );
}
