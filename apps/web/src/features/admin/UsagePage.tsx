import { useEffect, useState } from "react";
import { adminFetch } from "./adminFetch";

type UsageResponse = {
  group_by: string;
  items: Array<Record<string, string | number>>;
  totals: { input_tokens: number; output_tokens: number };
};

export function UsagePage() {
  const [groupBy, setGroupBy] = useState("route");
  const [data, setData] = useState<UsageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void adminFetch<UsageResponse>(`/admin/usage/tokens?group_by=${groupBy}`)
      .then(setData)
      .catch((err) => setError(String(err)));
  }, [groupBy]);

  return (
    <main className="page">
      <header>
        <h1>Token 用量</h1>
        <p className="lede">按 tenant / route / model 聚合；无上报数据时显示空列表。</p>
      </header>
      <label>
        group_by
        <select value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
          <option value="tenant">tenant</option>
          <option value="route">route</option>
          <option value="model">model</option>
        </select>
      </label>
      {error ? <p className="error">{error}</p> : null}
      {!data && !error ? <p className="muted">加载中…</p> : null}
      {data ? (
        <>
          {data.items.length === 0 ? (
            <p className="muted">暂无用量数据</p>
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
            合计 input={data.totals.input_tokens} output={data.totals.output_tokens}
          </p>
        </>
      ) : null}
    </main>
  );
}
