import { useCallback, useEffect, useMemo, useState } from "react";
import { useI18n } from "../../i18n";
import { adminFetch } from "./adminFetch";

type IngestJob = {
  job_id: string;
  status: string;
  ingested_count?: number;
  updated_at?: string;
};

type KnowledgeStatus = {
  backend?: string;
  healthy?: boolean;
  embedding?: { status?: string; model?: string | null; message?: string };
  ingest_jobs?: IngestJob[];
};

type KnowledgeHit = {
  chunk_id: string;
  doc_id: string;
  text: string;
  score?: number | null;
  metadata?: Record<string, unknown>;
};

const copy = {
  zh: {
    title: "知识库连接",
    intro: "确认检索服务可用，并导入一段真实资料后回到验证工作台测试引用结果。",
    connection: "连接状态",
    backend: "当前检索服务",
    ready: "后端已就绪",
    unavailable: "后端不可用",
    checking: "正在检查",
    embedding: "向量模型",
    notReported: "服务未返回模型信息",
    ingest: "导入测试资料",
    ingestHint: "导入会写入当前知识后端；Fake 仅用于离线演示，生产请连接 PostgreSQL 或 RAG-Agent。",
    text: "要导入的文本",
    textPlaceholder: "粘贴一段可被检索的业务资料，例如：高风险工单必须先经过值班主管审批。",
    source: "资料名称（可选）",
    sourcePlaceholder: "例如：工单审批规范",
    submit: "导入资料",
    submitting: "导入中…",
    jobs: "最近导入任务",
    noJobs: "还没有导入记录。",
    job: "任务",
    status: "状态",
    count: "结果",
    updated: "更新时间",
    completed: "已完成",
    running: "进行中",
    failed: "失败",
    imported: (count: number) => `已导入 ${count} 段`,
    refresh: "刷新状态",
    error: "无法读取知识服务状态。",
    ingestError: "导入失败，请检查知识服务连接和资料格式。",
    unsupported: "当前后端只读，不能从此处导入资料。",
    search: "测试检索",
    searchPlaceholder: "输入问题，查看当前租户能检索到的资料。",
    searchSubmit: "搜索",
    searching: "搜索中…",
    hits: "检索结果",
    noHits: "没有匹配结果。",
    searchError: "检索失败，请检查知识服务连接。",
  },
  en: {
    title: "Knowledge connection",
    intro: "Check retrieval, ingest a real piece of knowledge, then verify citation output in the workbench.",
    connection: "Connection",
    backend: "Retrieval service",
    ready: "Backend ready",
    unavailable: "Backend unavailable",
    checking: "Checking",
    embedding: "Embedding model",
    notReported: "No model reported",
    ingest: "Ingest test knowledge",
    ingestHint: "Ingest writes to the configured backend. Fake is for offline demos; production should use PostgreSQL or RAG-Agent.",
    text: "Text to ingest",
    textPlaceholder: "Paste searchable business knowledge, for example: High-risk work orders require supervisor approval.",
    source: "Source name (optional)",
    sourcePlaceholder: "For example: Work-order approval policy",
    submit: "Ingest knowledge",
    submitting: "Ingesting…",
    jobs: "Recent ingest jobs",
    noJobs: "No ingest jobs yet.",
    job: "Job",
    status: "Status",
    count: "Result",
    updated: "Updated",
    completed: "Completed",
    running: "Running",
    failed: "Failed",
    imported: (count: number) => `Ingested ${count} chunk${count === 1 ? "" : "s"}`,
    refresh: "Refresh status",
    error: "Could not read knowledge service status.",
    ingestError: "Ingest failed. Check the knowledge service and document format.",
    unsupported: "The configured backend is read-only; ingestion is unavailable here.",
    search: "Test retrieval",
    searchPlaceholder: "Ask a question to see what this tenant can retrieve.",
    searchSubmit: "Search",
    searching: "Searching…",
    hits: "Retrieved results",
    noHits: "No matching results.",
    searchError: "Search failed. Check the knowledge service connection.",
  },
} as const;

function backendLabel(value: string | undefined, locale: string): string {
  const labels: Record<string, string> = locale === "en"
    ? { fake: "Offline demo", langchain_pg: "AgentBridge PostgreSQL", rag_agent_pg: "RAG-Agent PostgreSQL", external: "External knowledge service" }
    : { fake: "离线演示", langchain_pg: "AgentBridge PostgreSQL", rag_agent_pg: "RAG-Agent PostgreSQL", external: "外部知识服务" };
  return labels[value ?? ""] ?? value ?? "未配置";
}

function statusLabel(
  status: string | undefined,
  text: Pick<typeof copy.zh, "completed" | "running" | "failed"> | Pick<typeof copy.en, "completed" | "running" | "failed">,
): string {
  if (status === "completed") return text.completed;
  if (status === "running") return text.running;
  if (status === "error") return text.failed;
  return status ?? "-";
}

export function KnowledgePage() {
  const { locale } = useI18n();
  const text = locale === "en" ? copy.en : copy.zh;
  const [data, setData] = useState<KnowledgeStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ingestText, setIngestText] = useState("");
  const [source, setSource] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<KnowledgeHit[]>([]);
  const [searching, setSearching] = useState(false);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      setData(await adminFetch<KnowledgeStatus>("/admin/knowledge/status"));
    } catch {
      setError(text.error);
    }
  }, [text.error]);

  useEffect(() => { void refresh(); }, [refresh]);

  const canIngest = useMemo(
    () => data?.backend === "fake" || data?.backend === "langchain_pg",
    [data?.backend],
  );

  async function submitIngest() {
    if (!ingestText.trim() || submitting) return;
    setSubmitting(true);
    setNotice(null);
    setError(null);
    try {
      const result = await adminFetch<{ ingested_count?: number }>("/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          docs: [{
            chunk_id: `console-${Date.now()}`,
            text: ingestText.trim(),
            metadata: source.trim() ? { source: source.trim() } : {},
          }],
        }),
      });
      setNotice(text.imported(Number(result.ingested_count ?? 0)));
      setIngestText("");
      setSource("");
      await refresh();
    } catch {
      setError(text.ingestError);
    } finally {
      setSubmitting(false);
    }
  }

  async function submitSearch() {
    if (!query.trim() || searching) return;
    setSearching(true);
    setError(null);
    try {
      const result = await adminFetch<{ hits?: KnowledgeHit[] }>("/admin/knowledge/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim(), limit: 5 }),
      });
      setHits(result.hits ?? []);
    } catch {
      setError(text.searchError);
    } finally {
      setSearching(false);
    }
  }

  const jobs = data?.ingest_jobs ?? [];
  return <main className="page knowledge-page">
    <header className="admin-hub-header"><div><p className="eyebrow">AgentBridge / {text.connection}</p><h1>{text.title}</h1><p className="lede">{text.intro}</p></div><button type="button" className="secondary" onClick={() => void refresh()}>{text.refresh}</button></header>
    {error ? <p className="error" role="alert">{error}</p> : null}
    {notice ? <p className="config-notice" role="status">{notice}</p> : null}
    <section className="admin-status knowledge-status"><h2>{text.connection}</h2><dl>
      <div><dt>{text.backend}</dt><dd>{backendLabel(data?.backend, locale)}</dd></div>
      <div><dt>{text.embedding}</dt><dd>{data?.embedding?.model || text.notReported}</dd></div>
      <div><dt>{text.status}</dt><dd className={data?.healthy ? "status-ok" : "status-error"}>{data ? (data.healthy ? text.ready : text.unavailable) : text.checking}</dd></div>
    </dl></section>
    <section className="config-section knowledge-ingest"><div className="config-section-heading"><div><h2>{text.ingest}</h2><p>{text.ingestHint}</p></div></div>
      {canIngest ? <div className="knowledge-form"><label><span>{text.text}</span><textarea aria-label={text.text} placeholder={text.textPlaceholder} rows={6} value={ingestText} onChange={(event) => setIngestText(event.target.value)} /></label><label><span>{text.source}</span><input aria-label={text.source} placeholder={text.sourcePlaceholder} value={source} onChange={(event) => setSource(event.target.value)} /></label><button type="button" className="primary" disabled={!ingestText.trim() || submitting} onClick={() => void submitIngest()}>{submitting ? text.submitting : text.submit}</button></div> : <p className="muted">{text.unsupported}</p>}
    </section>
    <section className="config-section knowledge-search"><div className="config-section-heading"><div><h2>{text.search}</h2></div></div>
      <div className="knowledge-form"><label><span>{text.search}</span><input aria-label={text.search} placeholder={text.searchPlaceholder} value={query} onChange={(event) => setQuery(event.target.value)} /></label><button type="button" className="primary" disabled={!query.trim() || searching} onClick={() => void submitSearch()}>{searching ? text.searching : text.searchSubmit}</button></div>
      <h3>{text.hits}</h3>
      {hits.length ? <div className="knowledge-hits">{hits.map((hit) => <article className="knowledge-hit" key={hit.chunk_id}><div><code>{hit.doc_id} / {hit.chunk_id}</code>{typeof hit.score === "number" ? <span>{hit.score.toFixed(2)}</span> : null}</div><p>{hit.text}</p>{hit.metadata && Object.keys(hit.metadata).length ? <small>{JSON.stringify(hit.metadata)}</small> : null}</article>)}</div> : <p className="muted">{text.noHits}</p>}
    </section>
    <section className="config-section"><div className="config-section-heading"><div><h2>{text.jobs}</h2></div></div>{jobs.length ? <table className="config-table"><thead><tr><th>{text.job}</th><th>{text.status}</th><th>{text.count}</th><th>{text.updated}</th></tr></thead><tbody>{jobs.map((job) => <tr key={job.job_id}><td><code>{job.job_id}</code></td><td>{statusLabel(job.status, text)}</td><td>{text.imported(Number(job.ingested_count ?? 0))}</td><td>{job.updated_at ? new Date(job.updated_at).toLocaleString(locale === "en" ? "en-US" : "zh-CN") : "-"}</td></tr>)}</tbody></table> : <p className="muted">{text.noJobs}</p>}</section>
  </main>;
}
