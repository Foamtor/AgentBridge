import { useEffect, useState } from "react";
import { adminFetch } from "./adminFetch";

type ToolRow = {
  name: string;
  domain: string;
  description: string;
  required_permissions: string[];
  required_roles: string[];
  invoke_allowed: boolean;
};

type ToolsResponse = {
  tools: ToolRow[];
  matrix: { roles: string[]; tools: Record<string, Record<string, string>> };
};

export function ToolsPage() {
  const [data, setData] = useState<ToolsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<ToolRow | null>(null);
  const [argsJson, setArgsJson] = useState("{}");
  const [invokeResult, setInvokeResult] = useState<string | null>(null);

  useEffect(() => {
    void adminFetch<ToolsResponse>("/admin/tools")
      .then(setData)
      .catch((err) => setError(String(err)));
  }, []);

  async function onInvoke() {
    if (!selected) return;
    setInvokeResult(null);
    try {
      const arguments_ = JSON.parse(argsJson) as Record<string, unknown>;
      const body = await adminFetch<{ ok: boolean; result: unknown }>(
        `/admin/tools/${encodeURIComponent(selected.name)}/invoke`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ arguments: arguments_ }),
        },
      );
      setInvokeResult(JSON.stringify(body.result, null, 2));
    } catch (err) {
      setInvokeResult(String(err));
    }
  }

  return (
    <main className="page">
      <header>
        <h1>Tools</h1>
        <p className="lede">工具目录与权限矩阵；试调需后端开启 ADMIN_TOOL_INVOKE_ENABLED。</p>
      </header>
      {error ? <p className="error">{error}</p> : null}
      {!data && !error ? <p className="muted">加载中…</p> : null}
      {data ? (
        <>
          <table className="config-table">
            <thead>
              <tr>
                <th>名称</th>
                <th>插件</th>
                <th>权限</th>
                <th>角色</th>
                <th>试调</th>
              </tr>
            </thead>
            <tbody>
              {data.tools.map((tool) => (
                <tr key={`${tool.domain}:${tool.name}`}>
                  <td>{tool.name}</td>
                  <td>{tool.domain}</td>
                  <td>{tool.required_permissions.join(", ") || "—"}</td>
                  <td>{tool.required_roles.join(", ") || "—"}</td>
                  <td>
                    <button type="button" onClick={() => setSelected(tool)}>
                      选择
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <h2>权限矩阵</h2>
          <table className="config-table">
            <thead>
              <tr>
                <th>Tool</th>
                {data.matrix.roles.map((role) => (
                  <th key={role}>{role}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.matrix.tools).map(([toolName, row]) => (
                <tr key={toolName}>
                  <td>{toolName}</td>
                  {data.matrix.roles.map((role) => (
                    <td key={role}>{row[role]}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {selected ? (
            <section>
              <h2>试调：{selected.name}</h2>
              {!selected.invoke_allowed ? (
                <p className="muted">后端未开启试调（ADMIN_TOOL_INVOKE_ENABLED=false）</p>
              ) : null}
              <label>
                arguments（JSON）
                <textarea
                  rows={4}
                  value={argsJson}
                  onChange={(e) => setArgsJson(e.target.value)}
                />
              </label>
              <div className="actions">
                <button
                  type="button"
                  disabled={!selected.invoke_allowed}
                  onClick={() => void onInvoke()}
                >
                  调用
                </button>
              </div>
              {invokeResult ? <pre>{invokeResult}</pre> : null}
            </section>
          ) : null}
        </>
      ) : null}
    </main>
  );
}
