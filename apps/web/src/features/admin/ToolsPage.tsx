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
    title: "Tools and permissions", intro: "Review plugin tools, required access, and the role matrix. Invocation requires ADMIN_TOOL_INVOKE_ENABLED.", name: "Name", domain: "Plugin", any: "Any of these permissions", all: "All of these permissions", roles: "Roles", select: "Select", loading: "Loading…", invoke: "Test tool", disabled: "Tool testing is disabled by the server.", args: "Arguments (JSON)", call: "Call", result: "Result", noExtra: "None", permissionRequired: "Depends on account permissions",
  } : {
    title: "工具与权限", intro: "查看插件工具、所需权限和角色矩阵。试调需要后端开启 ADMIN_TOOL_INVOKE_ENABLED。", name: "名称", domain: "插件", any: "满足任一权限", all: "必须同时具备", roles: "角色", select: "选择", loading: "加载中…", invoke: "试调工具", disabled: "后端未开启工具试调。", args: "参数（JSON）", call: "调用", result: "结果", noExtra: "无", permissionRequired: "取决于账号权限",
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
    <main className="page">
      <header>
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
            <section>
              <h2>{copy.invoke}: {selected.name}</h2>
              {!selected.invoke_allowed ? (
                <p className="muted">{copy.disabled}</p>
              ) : null}
              <label>
                {copy.args}
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
            </section>
          ) : null}
        </>
      ) : null}
    </main>
  );
}
