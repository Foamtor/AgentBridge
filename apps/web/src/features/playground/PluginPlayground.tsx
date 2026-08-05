import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useI18n } from "../../i18n";
import { apiBase } from "../../lib/apiBase";
import { streamChatSse, type StreamEvent } from "../../lib/sseClient";
import { getToken } from "../auth/token";
import { BusinessResults } from "../verification/BusinessResults";
import { EnvironmentSummary } from "../verification/EnvironmentSummary";
import { analyzeEvents, mergeAnswer } from "./analysis";
import { downloadRunEvents, playgroundFetch } from "./api";
import { playgroundCopy } from "./copy";
import { HistoryRail } from "./HistoryRail";
import { RequestComposer } from "./RequestComposer";
import { RunInspector } from "./RunInspector";
import type { ChatRequest, DiagnosticSummary, RunAnnotation, RunDiagnostics, RunRecord, ThreadMessage } from "./types";

function newThreadId(): string {
  return `t-${crypto.randomUUID().slice(0, 8)}`;
}

function initialRequest(): ChatRequest {
  return { query: "hello", thread_id: newThreadId(), route: "echo", model: "default", extra: {} };
}

function authHeaders(): Record<string, string> {
  const token = getToken().trim();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function PluginPlayground() {
  const { locale } = useI18n();
  const copy = playgroundCopy(locale);
  const [searchParams, setSearchParams] = useSearchParams();
  const [request, setRequest] = useState<ChatRequest>(initialRequest);
  const [extraText, setExtraText] = useState("{}");
  const [routes, setRoutes] = useState<Array<{ name: string; description: string }>>([{ name: "echo", description: "" }]);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [selectedRun, setSelectedRun] = useState<RunRecord | null>(null);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [messages, setMessages] = useState<ThreadMessage[]>([]);
  const [serverDiagnostics, setServerDiagnostics] = useState<RunDiagnostics | null>(null);
  const [annotations, setAnnotations] = useState<RunAnnotation[]>([]);
  const [summary, setSummary] = useState<DiagnosticSummary | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectionLoading, setSelectionLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const currentRunId = useRef<string | null>(null);

  const diagnostics = useMemo(() => events.length ? analyzeEvents(events) : serverDiagnostics, [events, serverDiagnostics]);
  const extraValid = useMemo(() => {
    try {
      const parsed: unknown = JSON.parse(extraText || "{}");
      return Boolean(parsed && !Array.isArray(parsed) && typeof parsed === "object");
    } catch {
      return false;
    }
  }, [extraText]);

  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const [runPage, domainPage, aggregate] = await Promise.all([
        playgroundFetch<{ items: RunRecord[] }>("/admin/runs?limit=100"),
        playgroundFetch<{ domains: Array<{ name: string; description: string }> }>("/admin/domains"),
        playgroundFetch<DiagnosticSummary>("/admin/diagnostics"),
      ]);
      setRuns(runPage.items);
      if (domainPage.domains.length) setRoutes(domainPage.domains);
      setSummary(aggregate);
    } catch (reason) {
      setError(`${copy.requestFailed}: ${String(reason)}`);
    } finally {
      setHistoryLoading(false);
    }
  }, [copy.requestFailed]);

  const selectRun = useCallback(async (run: RunRecord) => {
    setError(null); setFeedback(null); setSelectionLoading(true);
    try {
      const [fullRun, runEvents, runDiagnostics, runAnnotations, threadMessages] = await Promise.all([
        playgroundFetch<RunRecord>(`/runs/${encodeURIComponent(run.run_id)}`),
        playgroundFetch<StreamEvent[]>(`/runs/${encodeURIComponent(run.run_id)}/events`),
        playgroundFetch<RunDiagnostics>(`/runs/${encodeURIComponent(run.run_id)}/diagnostics`),
        playgroundFetch<RunAnnotation[]>(`/runs/${encodeURIComponent(run.run_id)}/annotations`),
        playgroundFetch<ThreadMessage[]>(`/threads/${encodeURIComponent(run.thread_id)}/messages`),
      ]);
      setSelectedRun(fullRun);
      setEvents(runEvents);
      setServerDiagnostics(runDiagnostics);
      setAnnotations(runAnnotations);
      setMessages(threadMessages.filter((message) => message.run_id === run.run_id));
      setSearchParams({ run_id: run.run_id }, { replace: true });
    } catch (reason) {
      setError(`${copy.requestFailed}: ${String(reason)}`);
    } finally {
      setSelectionLoading(false);
    }
  }, [copy.requestFailed, setSearchParams]);

  useEffect(() => { void refreshHistory(); }, [refreshHistory]);

  useEffect(() => {
    const requestedRunId = searchParams.get("run_id");
    if (!requestedRunId || !runs.length || selectedRun?.run_id === requestedRunId) return;
    const match = runs.find((run) => run.run_id === requestedRunId);
    if (match) void selectRun(match);
  }, [runs, searchParams, selectRun, selectedRun?.run_id]);

  function parseExtra(): Record<string, unknown> | null {
    try {
      const parsed: unknown = JSON.parse(extraText || "{}");
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("object required");
      return parsed as Record<string, unknown>;
    } catch {
      setError(copy.invalidJson);
      return null;
    }
  }

  async function send() {
    const extra = parseExtra();
    if (!extra) return;
    const payload = { ...request, extra };
    setRequest(payload);
    setError(null); setEvents([]); setMessages([]); setAnnotations([]); setServerDiagnostics(null); setSelectedRun(null);
    setBusy(true); currentRunId.current = null;
    setFeedback(null);
    const controller = new AbortController(); abortRef.current = controller;
    let succeeded = false;
    let streamFailed = false;
    try {
      await streamChatSse(`${apiBase()}/chat/stream`, {
        method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() }, body: JSON.stringify(payload),
      }, { onEvent: (event) => {
        currentRunId.current = event.run_id ?? currentRunId.current;
        setEvents((current) => [...current, event]);
        setSelectedRun((current) => current ?? { run_id: event.run_id ?? "live", thread_id: payload.thread_id, route: payload.route, trace_id: event.trace_id, status: event.type === "start" ? "running" : event.type, request: payload });
      }, onError: (reason) => { streamFailed = true; setError(String(reason)); } }, controller.signal);
      succeeded = !streamFailed;
    } catch (reason) {
      const detail = reason as { status?: number; message?: string };
      setError(detail.status === 409 ? copy.threadBusy : `${copy.requestFailed}: ${detail.message ?? String(reason)}`);
    } finally {
      setBusy(false); abortRef.current = null;
      await refreshHistory();
      const completedId = currentRunId.current;
      if (completedId) {
        const completed = (await playgroundFetch<RunRecord>(`/runs/${encodeURIComponent(completedId)}`).catch(() => null));
        if (completed) await selectRun(completed);
      }
      if (succeeded) setFeedback(copy.runComplete);
    }
  }

  async function cancel() {
    try {
      await playgroundFetch<{ ok: boolean }>("/chat/cancel", { method: "POST", body: JSON.stringify({ thread_id: request.thread_id, run_id: currentRunId.current }) });
    } catch (reason) {
      setError(`${copy.requestFailed}: ${String(reason)}`);
    } finally {
      abortRef.current?.abort();
    }
  }

  async function doubleFire() {
    const extra = parseExtra(); if (!extra) return;
    const body = JSON.stringify({ ...request, extra });
    const init = { method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() }, body, credentials: "include" as RequestCredentials };
    const first = fetch(`${apiBase()}/chat/stream`, init);
    await new Promise((resolve) => setTimeout(resolve, 40));
    try {
      const second = await fetch(`${apiBase()}/chat/stream`, init);
      setError(second.status === 409 ? copy.threadBusy : `${copy.requestFailed}: HTTP ${second.status}`);
    } finally {
      await playgroundFetch("/chat/cancel", { method: "POST", body: JSON.stringify({ thread_id: request.thread_id }) }).catch(() => undefined);
      void first;
    }
  }

  function loadSelectedRequest() {
    if (!selectedRun?.request) return;
    setRequest(selectedRun.request);
    setExtraText(JSON.stringify(selectedRun.request.extra ?? {}, null, 2));
  }

  async function copyCurl() {
    const extra = parseExtra(); if (!extra) return;
    const payload = JSON.stringify({ ...request, extra });
    await navigator.clipboard.writeText(`curl -N -X POST ${window.location.origin}${apiBase()}/chat/stream -H "Content-Type: application/json" -d '${payload}'`);
    setCopied(true); window.setTimeout(() => setCopied(false), 1400);
  }

  async function createAnnotation(body: { category: string; rating: string; reason: string; expected_behavior: string; tags: string[] }) {
    if (!selectedRun) return;
    const item = await playgroundFetch<RunAnnotation>(`/runs/${encodeURIComponent(selectedRun.run_id)}/annotations`, { method: "POST", body: JSON.stringify(body) });
    setAnnotations((current) => [item, ...current]);
    setFeedback(copy.saved);
    void refreshHistory();
  }

  async function deleteAnnotation(id: string) {
    if (!selectedRun) return;
    await playgroundFetch(`/runs/${encodeURIComponent(selectedRun.run_id)}/annotations/${encodeURIComponent(id)}`, { method: "DELETE" });
    setAnnotations((current) => current.filter((item) => item.annotation_id !== id));
    setFeedback(copy.saved);
    void refreshHistory();
  }

  async function exportEvents() {
    if (!selectedRun) return;
    setExporting(true); setFeedback(null);
    try {
      await downloadRunEvents(selectedRun.run_id);
      setFeedback(copy.exportDone);
    } catch (reason) {
      setError(`${copy.requestFailed}: ${String(reason)}`);
    } finally {
      setExporting(false);
    }
  }

  const answer = messages.find((message) => message.role === "assistant")?.content || mergeAnswer(events);
  const extensionEvents = events.filter((event) => event.type.startsWith("x.") && event.data && Object.keys(event.data).length);
  const statusLabel: Record<string, string> = { done: copy.statusDone, complete: copy.statusDone, awaiting_approval: copy.statusAwaitingApproval, waiting_approval: copy.statusAwaitingApproval, error: copy.statusError, cancelled: copy.statusCancelled };
  const currentStatus = busy ? copy.live : selectedRun ? (statusLabel[selectedRun.status] ?? selectedRun.status) : copy.pending;

  return <main className="plugin-playground">
    <header className="playground-header"><div><p className="eyebrow">{copy.live} / AgentBridge</p><h1>{copy.title}</h1><p>{copy.subtitle}</p></div><div className="active-run" aria-live="polite"><span>{copy.run}</span><code title={selectedRun?.run_id}>{selectedRun ? selectedRun.run_id : "-"}</code><span>{copy.status}</span><strong className={busy ? "status-running" : selectedRun ? `status-${selectedRun.status}` : ""}>{currentStatus}</strong></div></header>
    <EnvironmentSummary />
    <div className="playground-status-strip" role="status" aria-live="polite"><span className={`status-dot ${busy ? "is-running" : selectedRun ? `is-${selectedRun.status}` : ""}`} aria-hidden="true" /> <strong>{currentStatus}</strong>{feedback ? <span className="status-feedback">{feedback}</span> : null}{error ? <span className="status-feedback status-feedback-error">{error}</span> : null}</div>
    <div className="playground-grid">
      <HistoryRail copy={copy} runs={runs} selectedRunId={selectedRun?.run_id} search={search} status={status} summary={summary} loading={historyLoading} onSearch={setSearch} onStatus={setStatus} onSelect={(run) => void selectRun(run)} onRefresh={() => void refreshHistory()} />
      <div className="playground-main">
        <RequestComposer copy={copy} request={request} extraText={extraText} extraValid={extraValid} routes={routes} busy={busy} error={error} copied={copied} onRequest={setRequest} onExtraText={setExtraText} onSend={() => void send()} onCancel={() => void cancel()} onDoubleFire={() => void doubleFire()} onNewThread={() => setRequest((current) => ({ ...current, thread_id: newThreadId() }))} onLoad={loadSelectedRequest} onCopyCurl={() => void copyCurl()} canLoad={Boolean(selectedRun?.request)} />
        <section className="conversation-zone"><div className="section-title"><h2>{copy.answer}</h2>{busy ? <span className="live-indicator"><i />{copy.live}</span> : null}</div>{answer ? <div className="assistant-answer">{answer}</div> : <p className="empty-output">{copy.emptyAnswer}</p>}
          {selectedRun?.route === "work_order_ops" && events.length ? <details className="business-renderer"><summary>{copy.workOrderResult}</summary><BusinessResults events={events} token="" onPreset={() => undefined} showPresets={false} /></details> : null}
          {extensionEvents.length ? <details className="structured-extensions"><summary>{copy.extensions} ({extensionEvents.length})</summary>{extensionEvents.map((event, index) => <div key={event.event_id ?? index}><code>{event.type}</code><pre>{JSON.stringify(event.data, null, 2)}</pre></div>)}</details> : null}
        </section>
      </div>
      <RunInspector copy={copy} run={selectedRun} events={events} diagnostics={diagnostics} annotations={annotations} loading={selectionLoading} exporting={exporting} onCreateAnnotation={createAnnotation} onDeleteAnnotation={deleteAnnotation} onExportEvents={exportEvents} />
    </div>
  </main>;
}
