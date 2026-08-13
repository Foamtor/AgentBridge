import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useI18n } from "../../i18n";
import { adminErrorMessage, adminFetch } from "./adminFetch";

type ToolDetail = {
  name: string;
  description: string;
  required_roles: string[];
  required_permissions: string[];
  required_permissions_all: string[];
};

type ApprovalAction = {
  type: string;
  resource: { name?: string; required_roles?: string[]; required_permissions?: string[]; required_permissions_all?: string[] };
};

type Domain = {
  name: string;
  description: string;
  tools: string[];
  tool_details?: ToolDetail[];
  approval_actions?: ApprovalAction[];
  graph_registered: boolean;
};

const zh = {
  title: "已加载的业务能力",
  intro: "这里显示当前 API 进程已从源码加载的插件。插件的创建和修改在代码目录中完成；保存后重启 API，再回到这里确认是否已加载。",
  source: "来源",
  starter: "起步样例",
  demo: "内置演示",
  reference: "完整参考",
  custom: "自定义插件",
  ready: "已加载",
  unavailable: "未加载",
  capabilities: "业务说明",
  tools: "模型可用工具",
  noTools: "这个插件没有公开给模型的工具；它通过自身流程图完成处理，并非缺少配置。",
  noRequirement: "无需额外权限",
  anyPermission: (items: string[]) => `具备其中任一权限：${items.join("、")}`,
  allPermission: (items: string[]) => `必须同时具备：${items.join("、")}`,
  roles: (items: string[]) => `角色限制：${items.join("、")}`,
  approval: "人工审批动作",
  noApproval: "没有登记需要平台审批的写入动作。",
  approvalRule: (action: ApprovalAction) => action.resource.required_permissions_all?.length ? `必须同时具备：${action.resource.required_permissions_all.join("、")}` : action.resource.required_permissions?.length ? `具备其中任一权限：${action.resource.required_permissions.join("、")}` : "审批后执行",
  test: "在调试场测试",
  policies: "查看工具权限",
  loading: "正在读取已加载的插件…",
  noDescription: "未提供业务说明。",
};

const en: typeof zh = {
  title: "Loaded business capabilities",
  intro: "This page shows plugins the current API process loaded from source. Create and edit plugins in the source tree, restart the API, then return here to confirm they loaded.",
  source: "Source",
  starter: "Starter example",
  demo: "Bundled demo",
  reference: "Complete reference",
  custom: "Custom plugin",
  ready: "Loaded",
  unavailable: "Not loaded",
  capabilities: "Business purpose",
  tools: "Tools available to the model",
  noTools: "This plugin exposes no tools to the model. Its graph handles the work itself; this is not a missing configuration.",
  noRequirement: "No additional permission required",
  anyPermission: (items: string[]) => `Any of: ${items.join(", ")}`,
  allPermission: (items: string[]) => `All required: ${items.join(", ")}`,
  roles: (items: string[]) => `Restricted to roles: ${items.join(", ")}`,
  approval: "Human approval actions",
  noApproval: "No platform approval-gated write action is registered.",
  approvalRule: (action: ApprovalAction) => action.resource.required_permissions_all?.length ? `All required: ${action.resource.required_permissions_all.join(", ")}` : action.resource.required_permissions?.length ? `Any of: ${action.resource.required_permissions.join(", ")}` : "Runs after approval",
  test: "Test in playground",
  policies: "View tool permissions",
  loading: "Reading loaded plugins…",
  noDescription: "No business description provided.",
};

function sourceLabel(name: string, copy: typeof zh): string {
  if (name === "echo") return copy.starter;
  if (name === "work_order_ops") return copy.reference;
  if (name.startsWith("demo_")) return copy.demo;
  return copy.custom;
}

function ToolRules({ tool, copy }: { tool: ToolDetail; copy: typeof zh }) {
  const rules = [
    tool.required_permissions.length ? copy.anyPermission(tool.required_permissions) : "",
    tool.required_permissions_all.length ? copy.allPermission(tool.required_permissions_all) : "",
    tool.required_roles.length ? copy.roles(tool.required_roles) : "",
  ].filter(Boolean);
  return <li><div><strong>{tool.name}</strong>{tool.description ? <small>{tool.description}</small> : null}</div><p>{rules.length ? rules.join("; ") : copy.noRequirement}</p></li>;
}

export function DomainsPage() {
  const { locale } = useI18n();
  const copy = locale === "en" ? en : zh;
  const [domains, setDomains] = useState<Domain[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void adminFetch<{ domains: Domain[] }>("/admin/domains")
      .then((body) => setDomains(body.domains))
      .catch((err) => setError(adminErrorMessage(err, locale)));
  }, [locale]);

  return <main className="page domains-page">
    <header className="domains-header"><div><p className="eyebrow">AgentBridge / {copy.source}</p><h1>{copy.title}</h1><p className="lede">{copy.intro}</p></div><Link className="primary" to="/playground">{copy.test} -&gt;</Link></header>
    {error ? <p className="error">{error}</p> : null}
    {!domains.length && !error ? <p className="muted">{copy.loading}</p> : null}
    <div className="domain-list">{domains.map((domain) => {
      const tools = domain.tool_details ?? domain.tools.map((name) => ({ name, description: "", required_roles: [], required_permissions: [], required_permissions_all: [] }));
      const actions = domain.approval_actions ?? [];
      return <article className="domain-record" key={domain.name}>
        <header><div><div className="domain-title"><h2>{domain.name}</h2><span className="domain-origin">{sourceLabel(domain.name, copy)}</span><span className={domain.graph_registered ? "domain-state" : "domain-state domain-state-error"}>{domain.graph_registered ? copy.ready : copy.unavailable}</span></div><p>{domain.description || copy.noDescription}</p></div><div className="domain-actions"><Link to={`/playground?route=${encodeURIComponent(domain.name)}`}>{copy.test}</Link><Link to={`/tools?route=${encodeURIComponent(domain.name)}`}>{copy.policies}</Link></div></header>
        <div className="domain-facts"><section><h3>{copy.tools}</h3>{tools.length ? <ul className="domain-tools">{tools.map((tool) => <ToolRules tool={tool} copy={copy} key={tool.name} />)}</ul> : <p className="domain-empty">{copy.noTools}</p>}</section><section><h3>{copy.approval}</h3>{actions.length ? <ul className="domain-approvals">{actions.map((action) => <li key={action.type}><strong>{action.resource.name || action.type}</strong><small>{action.type}</small><p>{copy.approvalRule(action)}</p></li>)}</ul> : <p className="domain-empty">{copy.noApproval}</p>}</section></div>
      </article>;
    })}</div>
  </main>;
}
