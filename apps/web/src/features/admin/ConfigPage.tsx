import { useEffect, useState } from "react";
import { adminFetch } from "./adminFetch";

type ConfigItem = {
  key: string;
  value: unknown;
  tier: string;
  description: string;
  configured?: boolean;
  writable?: boolean;
};

export function ConfigPage() {
  const [items, setItems] = useState<ConfigItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void adminFetch<{ items: ConfigItem[] }>("/admin/config")
      .then((body) => setItems(body.items))
      .catch((err) => setError(String(err)));
  }, []);

  return (
    <main className="page">
      <header>
        <h1>配置（只读）</h1>
        <p className="lede">C0 仅展示档 B/C 配置；密钥类项不明文显示。</p>
      </header>
      {error ? <p className="error">{error}</p> : null}
      {!items.length && !error ? <p className="muted">加载中…</p> : null}
      <table className="config-table">
        <thead>
          <tr>
            <th>键</th>
            <th>档</th>
            <th>值</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.key}>
              <td>{item.key}</td>
              <td>{item.tier}</td>
              <td>
                {item.tier === "C"
                  ? item.configured
                    ? "已配置"
                    : "未配置"
                  : String(item.value ?? "—")}
                {item.writable ? <span className="muted"> · 可编辑</span> : null}
              </td>
              <td className="muted">{item.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
