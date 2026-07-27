import { useEffect, useState } from "react";
import { adminFetch } from "./adminFetch";

type Domain = {
  name: string;
  description: string;
  tools: string[];
  required_permissions: string[];
  graph_registered: boolean;
};

export function DomainsPage() {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void adminFetch<{ domains: Domain[] }>("/admin/domains")
      .then((body) => setDomains(body.domains))
      .catch((err) => setError(String(err)));
  }, []);

  return (
    <main className="page">
      <header>
        <h1>业务插件</h1>
        <p className="lede">已注册 route、工具与权限摘要。</p>
      </header>
      {error ? <p className="error">{error}</p> : null}
      {!domains.length && !error ? <p className="muted">加载中…</p> : null}
      <ul className="timeline">
        {domains.map((d) => (
          <li key={d.name}>
            <strong>{d.name}</strong>
            {d.graph_registered ? null : <span className="muted"> · 图未注册</span>}
            <p className="muted">{d.description || "（无描述）"}</p>
            <p>
              工具：{d.tools.length ? d.tools.join(", ") : "—"}
            </p>
            <p>
              权限：
              {d.required_permissions.length ? d.required_permissions.join(", ") : "—"}
            </p>
          </li>
        ))}
      </ul>
    </main>
  );
}
