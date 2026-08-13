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
  const copy = locale === "en" ? { title: "Token usage", intro: "View this tenant's recorded usage by capability or model.", group: "Group by", tenant: "Tenant", route: "Capability", model: "Model", loading: "Loading…", empty: "No usage data", input: "Input", output: "Output", error: "Could not load token usage." } : { title: "Token 用量", intro: "按业务能力或模型查看当前租户已记录的用量。", group: "分组方式", tenant: "租户", route: "业务能力", model: "模型", loading: "加载中…", empty: "暂无用量数据", input: "输入", output: "输出", error: "无法读取 Token 用量。" };
  const [groupBy, setGroupBy] = useState("route");
  const [data, setData] = useState<UsageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void adminFetch<UsageResponse>(`/admin/usage/tokens?group_by=${groupBy}`)
      .then(setData)
      .catch(() => setError(copy.error));
  }, [groupBy, copy.error]);

  return (
    <main className="page">
      <header>
        <h1>{copy.title}</h1>
        <p className="lede">{copy.intro}</p>
      </header>
      <label>
        {copy.group}
        <select value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
          <option value="tenant">{copy.tenant}</option>
          <option value="route">{copy.route}</option>
          <option value="model">{copy.model}</option>
        </select>
      </label>
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
          <p className="muted">
            {copy.input}={data.totals.input_tokens} · {copy.output}={data.totals.output_tokens}
          </p>
        </>
      ) : null}
    </main>
  );
}
