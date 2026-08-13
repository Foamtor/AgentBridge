import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { adminErrorMessage, adminFetch } from "./adminFetch";
import { useI18n } from "../../i18n";

type ToolRow = {
  tool_id?: string;
  name: string;
  domain: string;
  description: string;
  required_permissions: string[];
  required_permissions_all: string[];
  required_roles: string[];
  invoke_allowed: boolean;
};

type ToolsResponse = {
  tools: ToolRow[];
  matrix: { roles: string[]; tools: Record<string, Record<string, string>> };
};

export function ToolsPage() {
  const { locale } = useI18n();
  const copy = locale === "en" ? {
    title: "Tool permissions", intro: "Review what each plugin tool does, who can call it, and whether approval is required. Direct tool calls are an advanced diagnostic and may have side effects.", name: "Tool", domain: "Plugin", any: "Any of these permissions", all: "All of these permissions", roles: "Roles", select: "Advanced test", loading: "Loading…", invoke: "Advanced tool test", disabled: "Tool testing is disabled by the server.", args: "Arguments (JSON)", call: "Call tool", result: "Result", noExtra: "None", permissionRequired: "Depends on account permissions", matrix: "Permission matrix", advancedHint: "This bypasses the model and does not represent a complete plugin flow. Use only with safe test data.", close: "Close",
  } : {
    title: "工具权限", intro: "查看每个插件工具的作用、可调用对象和审批要求。直接调用属于高级排障操作，可能产生业务副作用。", name: "工具", domain: "插件", any: "满足任一权限", all: "必须同时具备", roles: "角色", select: "高级试调", loading: "加载中…", invoke: "高级工具试调", disabled: "后端未开启工具试调。", args: "参数（JSON）", call: "调用工具", result: "调用结果", noExtra: "无", permissionRequired: "取决于账号权限", matrix: "权限矩阵", advancedHint: "此操作会绕过模型，不代表完整插件流程。请只使用安全的测试数据。", close: "关闭",
  };
  const [searchParams] = useSearchParams();
  const routeFilter = searchParams.get("route") ?? "";
  const [data, setData] = useState<ToolsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<ToolRow | null>(null);
  const [argsJson, setArgsJson] = useState("{}");
  const [invokeResult, setInvokeResult] = useState<string | null>(null);

  useEffect(() => {
    void adminFetch<ToolsResponse>("/admin/tools")
      .then(setData)
      .catch((err) => setError(adminErrorMessage(err, locale)));
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
          body: JSON.stringify({ route: selected.domain, arguments: arguments_ }),
        },
      );
      setInvokeResult(JSON.stringify(body.result, null, 2));
    } catch (err) {
      setInvokeResult(adminErrorMessage(err, locale));
    }
  }

  const visibleTools = data?.tools.filter((tool) => !routeFilter || tool.domain === routeFilter) ?? [];

  return (
    <main className="page admin-subpage tools-page">
      <header className="admin-page-header">
        <h1>{copy.title}</h1>
        <p className="lede">{routeFilter ? `${routeFilter} · ` : ""}{copy.intro}</p>
      </header>
      {error ? <p className="error">{error}</p> : null}
      {!data && !error ? <p className="muted">{copy.loading}</p> : null}
      {data ? (
        <>
          <table className="config-table">
            <thead>
              <tr>
                <th>{copy.name}</th><th>{copy.domain}</th><th>{copy.any}</th><th>{copy.all}</th><th>{copy.roles}</th><th>{copy.invoke}</th>
              </tr>
            </thead>
            <tbody>
              {visibleTools.map((tool) => (
                <tr key={`${tool.domain}:${tool.name}`}>
                  <td>{tool.name}</td>
                  <td>{tool.domain}</td>
                  <td>{tool.required_permissions.join(", ") || copy.noExtra}</td>
                  <td>{tool.required_permissions_all.join(", ") || copy.noExtra}</td>
                  <td>{tool.required_roles.join(", ") || copy.noExtra}</td>
                  <td>
                    <button type="button" onClick={() => setSelected(tool)}>
                      {copy.select}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <h2>{copy.matrix}</h2>
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
              {visibleTools.map((tool) => {
                const toolId = tool.tool_id ?? `${tool.domain}:${tool.name}`;
                const row = data.matrix.tools[toolId];
                if (!row) return null;
                return <tr key={toolId}>
                  <td>{tool.domain} / {tool.name}</td>
                  {data.matrix.roles.map((role) => (
                    <td key={role}>{row[role] === "permission_required" ? copy.permissionRequired : row[role]}</td>
                  ))}
                </tr>;
              })}
            </tbody>
          </table>
          {selected ? (
            <section className="tool-invoke-panel">
              <h2>{copy.invoke}: {selected.name}</h2>
              <p className="muted">{copy.advancedHint}</p>
              {!selected.invoke_allowed ? (
                <p className="muted">{copy.disabled}</p>
              ) : null}
              <label className="admin-editor-content">
                <span>{copy.args}</span>
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
                  {copy.call}
                </button>
              </div>
              {invokeResult ? <><h3>{copy.result}</h3><pre>{invokeResult}</pre></> : null}
              <button type="button" className="secondary-command" onClick={() => { setSelected(null); setInvokeResult(null); }}>{copy.close}</button>
            </section>
          ) : null}
        </>
      ) : null}
    </main>
  );
}
