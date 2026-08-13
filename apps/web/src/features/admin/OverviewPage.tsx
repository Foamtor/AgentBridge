import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useI18n } from "../../i18n";
import { adminErrorMessage, adminFetch } from "./adminFetch";

type Overview = {
  domains: { registered: number; graph_ready: number };
  llm_backend: { type: string; status: string };
  knowledge_backend: { type: string; status: string; message?: string };
  infra_ready: { status: string; checks: Record<string, { status: string; reason?: string }> };
  runs_24h: { total: number; errors: number };
  recent_failed_runs: Array<{
    run_id: string;
    route: string;
    status: string;
    started_at?: string;
  }>;
};

type AdminCopy = {
  title: string;
  intro: string;
  attention: string;
  attentionRuns: (count: number) => string;
  openRuns: string;
  setup: string;
  setupIntro: string;
  model: string;
  modelDesc: string;
  knowledge: string;
  knowledgeDesc: string;
  config: string;
  configDesc: string;
  connect: string;
  connectIntro: string;
  plugins: string;
  pluginsDesc: string;
  prompts: string;
  promptsDesc: string;
  tools: string;
  toolsDesc: string;
  observe: string;
  observeIntro: string;
  runs: string;
  runsDesc: string;
  usage: string;
  usageDesc: string;
  status: string;
  domains: string;
  runs24h: string;
  llm: string;
  infra: string;
  domainState: (registered: number, ready: number) => string;
  runState: (total: number, failed: number) => string;
  loading: string;
  noFailures: string;
  recentFailures: string;
  open: string;
  ready: string;
  unavailable: string;
  skipped: string;
};

const zh: AdminCopy = {
  title: "管理中心",
  intro: "从这里配置接入、检查运行状态，并定位需要处理的问题。",
  attention: "需要处理",
  attentionRuns: (count) => `近 24 小时有 ${count} 条运行失败`,
  openRuns: "查看运行记录",
  setup: "先配置，才能进行真实验证",
  setupIntro: "连接模型和知识服务，验证工作台即可使用真实能力。",
  model: "模型连接",
  modelDesc: "填写 API 地址、模型名和密钥；密钥只保存加密结果。",
  knowledge: "知识服务",
  knowledgeDesc: "检查检索后端是否就绪，以及知识数据能否被案例使用。",
  config: "平台配置",
  configDesc: "查看运行模式、认证和其他底层配置状态。",
  connect: "插件治理",
  connectIntro: "确认插件、提示词和工具权限，保证模型只使用允许的能力。",
  plugins: "已加载插件",
  pluginsDesc: "确认源码插件是否加载，并查看它提供的业务能力。",
  prompts: "提示词管理",
  promptsDesc: "管理会影响真实业务流程的模型行为提示词。",
  tools: "工具权限",
  toolsDesc: "查看工具用途、调用权限和审批要求。",
  observe: "运维诊断",
  observeIntro: "查看失败运行、Token 用量和需要排查的运行状态。",
  runs: "运行记录",
  runsDesc: "按状态查看失败运行，并打开调试详情检查完整链路。",
  usage: "Token 用量",
  usageDesc: "按租户、业务能力或模型查看已上报的用量。",
  status: "当前状态",
  domains: "已加载插件",
  runs24h: "近 24 小时运行",
  llm: "模型服务",
  infra: "基础设施",
  domainState: (registered, ready) => `已接入 ${registered} 个，可运行 ${ready} 个`,
  runState: (total, failed) => `共 ${total} 条，其中失败 ${failed} 条`,
  loading: "正在读取状态…",
  noFailures: "近 24 小时没有失败运行。",
  recentFailures: "最近失败运行",
  open: "打开",
  ready: "就绪",
  unavailable: "不可用",
  skipped: "未启用",
};

const en: AdminCopy = {
  title: "Admin center",
  intro: "Configure integrations, check runtime health, and resolve issues from one place.",
  attention: "Needs attention",
  attentionRuns: (count) => `${count} run${count === 1 ? "" : "s"} failed in the last 24 hours`,
  openRuns: "View run records",
  setup: "Configure this before a real-model test",
  setupIntro: "Connect a model and knowledge service before testing live capabilities.",
  model: "Model connection",
  modelDesc: "Enter the API address, model name, and key; keys are stored encrypted.",
  knowledge: "Knowledge service",
  knowledgeDesc: "Check whether retrieval is ready for the bundled verification cases.",
  config: "Platform configuration",
  configDesc: "Inspect runtime mode, authentication, and other base settings.",
  connect: "Plugin governance",
  connectIntro: "Review plugins, prompts, and permissions so models only use allowed capabilities.",
  plugins: "Loaded plugins",
  pluginsDesc: "Confirm source plugins are loaded and review the capabilities they provide.",
  prompts: "Prompt management",
  promptsDesc: "Manage model behavior prompts that affect real business flows.",
  tools: "Tool permissions",
  toolsDesc: "Review tool purpose, caller permissions, and approval requirements.",
  observe: "Operations diagnostics",
  observeIntro: "Review failed runs, token usage, and runtime issues that need attention.",
  runs: "Run records",
  runsDesc: "Find failed runs and open their complete debug timeline.",
  usage: "Token usage",
  usageDesc: "Review reported usage by tenant, capability, or model.",
  status: "Current status",
  domains: "Loaded plugins",
  runs24h: "Runs in the last 24 hours",
  llm: "Model service",
  infra: "Infrastructure",
  domainState: (registered, ready) => `${registered} connected, ${ready} ready`,
  runState: (total, failed) => `${total} total, ${failed} failed`,
  loading: "Reading status…",
  noFailures: "No failed runs in the last 24 hours.",
  recentFailures: "Recent failed runs",
  open: "Open",
  ready: "Ready",
  unavailable: "Unavailable",
  skipped: "Not enabled",
};

type AdminLink = { to: string; title: string; description: string };

function AdminSection({ title, intro, links }: { title: string; intro: string; links: AdminLink[] }) {
  return <section className="admin-section">
    <div className="admin-section-heading"><div><h2>{title}</h2><p>{intro}</p></div></div>
    <div className="admin-link-list">{links.map((item) => <Link className="admin-action" to={item.to} key={item.to}>
      <span><strong>{item.title}</strong><small>{item.description}</small></span><b aria-hidden="true">-&gt;</b>
    </Link>)}</div>
  </section>;
}

function statusText(value: string, copy: AdminCopy): string {
  if (value === "ok" || value === "ready") return copy.ready;
  if (value === "skipped") return copy.skipped;
  return copy.unavailable;
}

export function OverviewPage() {
  const { locale } = useI18n();
  const copy = locale === "en" ? en : zh;
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void adminFetch<Overview>("/admin/overview")
      .then(setData)
      .catch((err) => setError(adminErrorMessage(err, locale)));
  }, [locale]);

  const failedRuns = data?.runs_24h.errors ?? 0;
  return <main className="page admin-hub">
    <header className="admin-hub-header"><div><p className="eyebrow">AgentBridge / {copy.status}</p><h1>{copy.title}</h1><p className="lede">{copy.intro}</p></div><Link className="primary admin-quick-link" to="/models">{copy.model} -&gt;</Link></header>
    {error ? <p className="error">{error}</p> : null}
    {data && failedRuns > 0 ? <section className="admin-alert" role="status"><div><strong>{copy.attention}</strong><span>{copy.attentionRuns(failedRuns)}</span></div><Link to="/runs">{copy.openRuns} -&gt;</Link></section> : null}
    <AdminSection title={copy.setup} intro={copy.setupIntro} links={[
      { to: "/models", title: copy.model, description: copy.modelDesc },
      { to: "/knowledge", title: copy.knowledge, description: copy.knowledgeDesc },
      { to: "/config", title: copy.config, description: copy.configDesc },
    ]} />
    <AdminSection title={copy.connect} intro={copy.connectIntro} links={[
      { to: "/domains", title: copy.plugins, description: copy.pluginsDesc },
      { to: "/prompts", title: copy.prompts, description: copy.promptsDesc },
      { to: "/tools", title: copy.tools, description: copy.toolsDesc },
    ]} />
    <AdminSection title={copy.observe} intro={copy.observeIntro} links={[
      { to: "/runs", title: copy.runs, description: copy.runsDesc },
      { to: "/usage", title: copy.usage, description: copy.usageDesc },
    ]} />
    {data ? <section className="admin-status"><h2>{copy.status}</h2><dl>
      <div><dt>{copy.domains}</dt><dd>{copy.domainState(data.domains.registered, data.domains.graph_ready)}</dd></div>
      <div><dt>{copy.runs24h}</dt><dd>{copy.runState(data.runs_24h.total, failedRuns)}</dd></div>
      <div><dt>{copy.llm}</dt><dd>{data.llm_backend.type} · {statusText(data.llm_backend.status, copy)}</dd></div>
      <div><dt>{copy.infra}</dt><dd>{statusText(data.infra_ready.status, copy)}</dd></div>
    </dl></section> : !error ? <p className="muted">{copy.loading}</p> : null}
    {data && data.recent_failed_runs.length ? <section className="admin-failures"><h2>{copy.recentFailures}</h2><ul className="timeline">{data.recent_failed_runs.map((run) => <li key={run.run_id}><Link to={`/playground?run_id=${encodeURIComponent(run.run_id)}`}><strong>{run.run_id}</strong></Link><span> · {run.route} · {run.status}</span>{run.started_at ? <small className="muted"> · {run.started_at}</small> : null}<Link className="failure-open" to={`/playground?run_id=${encodeURIComponent(run.run_id)}`}>{copy.open}</Link></li>)}</ul></section> : data ? <p className="muted admin-no-failures">{copy.noFailures}</p> : null}
  </main>;
}
