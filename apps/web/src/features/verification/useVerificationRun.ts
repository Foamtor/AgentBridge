import { useMemo, useReducer, useRef, useState } from "react";
import { apiBase } from "../../lib/apiBase";
import { streamChatSse } from "../../lib/sseClient";
import { initialVerificationState, verificationReducer } from "./reducer";

export type VerificationScenario = "list" | "chart" | "knowledge" | "draft";
export type VerificationMode = "fake" | "real";

const SCENARIOS: Record<VerificationScenario, { query: string; extra: Record<string, unknown> }> = {
  list: { query: "show work orders", extra: {} },
  chart: { query: "show work orders as a pie chart", extra: {} },
  knowledge: { query: "search the work-order SOP", extra: {} },
  draft: {
    query: "create a synthetic work order for the demo",
    extra: { work_order_draft: { title: "Synthetic demo follow-up", priority: "medium", assignee_id: "assignee-dev-a", ledger_summary: "Created from the AgentBridge v0.1 demo" } },
  },
};

const REAL_DRAFT_QUERY = "Create a work order titled Network follow-up, priority medium, assign it to assignee-dev-a, and use the ledger summary Real model validation.";

function newThreadId(): string {
  return `verify-${crypto.randomUUID().slice(0, 8)}`;
}

export function useVerificationRun() {
  const [threadId] = useState(newThreadId);
  const [scenario, setScenario] = useState<VerificationScenario>("chart");
  const [mode, setMode] = useState<VerificationMode>("fake");
  const [verification, dispatch] = useReducer(verificationReducer, initialVerificationState);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const definition = SCENARIOS[scenario];
  const streamUrl = useMemo(() => `${apiBase()}/chat/stream`, []);
  const cancelUrl = useMemo(() => `${apiBase()}/chat/cancel`, []);

  async function run() {
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy(true);
    setError(null);
    dispatch({ type: "start" });
    try {
      const query = mode === "real" && scenario === "draft" ? REAL_DRAFT_QUERY : definition.query;
      const extra = mode === "real" ? { case_mode: "real" } : { ...definition.extra, case_mode: "fake" };
      await streamChatSse(streamUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, thread_id: threadId, route: "work_order_ops", extra }),
      }, {
        onEvent: (event) => dispatch({ type: "event", event }),
        onError: (cause) => setError(String(cause)),
      }, controller.signal);
    } catch (cause) {
      const failure = cause as { status?: number; message?: string };
      setError(failure.status === 409 ? "thread_busy" : failure.message ?? String(cause));
      dispatch({ type: "error", message: failure.message ?? String(cause) });
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  }

  async function cancel() {
    try {
      await fetch(cancelUrl, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ thread_id: threadId }) });
    } finally {
      abortRef.current?.abort();
    }
  }

  return { scenario, setScenario, mode, setMode, threadId, verification, busy, error, run, cancel };
}
