import { useEffect, useState } from "react";
import { adminFetch } from "./adminFetch";
import { useI18n } from "../../i18n";

type UsageResponse = {
  group_by: string;
  items: Array<Record<string, string | number>>;
  totals: { input_tokens: number; output_tokens: number };
};

export function UsagePage() {
  const { locale } = useI18n();
  const copy = locale === "en" ? { title: "Token usage", intro: "Review recorded real-model usage. Fake demo runs do not call an external model.", group: "Group by", tenant: "Tenant", route: "Plugin", model: "Model", loading: "Loading…", empty: "No usage data for this period.", input: "Input tokens", output: "Output tokens", total: "Total tokens", from: "From", until: "To", refresh: "Refresh", error: "Could not load token usage." } : { title: "Token 用量", intro: "查看真实模型的 Token 记录；Fake 演示不会调用外部模型。", group: "分组方式", tenant: "租户", route: "插件", model: "模型", loading: "正在读取用量…", empty: "这个时间范围内没有用量数据。", input: "输入 Token", output: "输出 Token", total: "总 Token", from: "开始日期", until: "结束日期", refresh: "刷新", error: "无法读取 Token 用量。" };
  const [groupBy, setGroupBy] = useState("route");
  const [data, setData] = useState<UsageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    const params = new URLSearchParams({ group_by: groupBy });
    if (since) params.set("since", new Date(`${since}T00:00:00`).toISOString());
    if (until) params.set("until", new Date(`${until}T23:59:59`).toISOString());
    void adminFetch<UsageResponse>(`/admin/usage/tokens?${params.toString()}`)
      .then((response) => {
        if (active) {
          setError(null);
          setData(response);
        }
      })
      .catch(() => {
        if (active) setError(copy.error);
      });
    return () => {
      active = false;
    };
  }, [groupBy, since, until, refresh, copy.error]);

  return (
    <main className="page admin-subpage usage-page">
      <header className="admin-page-header">
        <h1>{copy.title}</h1>
        <p className="lede">{copy.intro}</p>
      </header>
      <label className="usage-group">
        {copy.group}
        <select value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
          <option value="tenant">{copy.tenant}</option>
          <option value="route">{copy.route}</option>
          <option value="model">{copy.model}</option>
        </select>
      </label>
      <div className="session-bar"><label>{copy.from}<input type="date" value={since} onChange={(e) => setSince(e.target.value)} /></label><label>{copy.until}<input type="date" value={until} onChange={(e) => setUntil(e.target.value)} /></label><button type="button" className="secondary-command" onClick={() => setRefresh((value) => value + 1)}>{copy.refresh}</button></div>
      {error ? <p className="error">{error}</p> : null}
      {!data && !error ? <p className="muted">{copy.loading}</p> : null}
      {data ? (
        <>
          {data.items.length === 0 ? (
            <p className="muted">{copy.empty}</p>
          ) : (
            <table className="config-table">
              <thead>
                <tr>
                  {Object.keys(data.items[0]).map((key) => (
                    <th key={key}>{key}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.items.map((row, idx) => (
                  <tr key={idx}>
                    {Object.values(row).map((val, i) => (
                      <td key={i}>{String(val)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="muted">{copy.input}={data.totals.input_tokens} · {copy.output}={data.totals.output_tokens} · {copy.total}={data.totals.input_tokens + data.totals.output_tokens}</p>
        </>
      ) : null}
    </main>
  );
}
