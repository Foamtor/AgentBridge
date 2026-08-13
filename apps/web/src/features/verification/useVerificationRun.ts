import { useMemo, useReducer, useRef, useState } from "react";
import { apiBase } from "../../lib/apiBase";
import { streamChatSse } from "../../lib/sseClient";
import { initialVerificationState, verificationReducer } from "./reducer";

export type VerificationScenario = "list" | "chart" | "knowledge" | "draft" | "routing";
export type VerificationMode = "fake" | "real";
export type RouteDecision = {
  route: string | null;
  reason: string;
  expected_tools: string[];
  candidates: Array<{ route?: string; score?: number; matched_keywords?: string[]; expected_tools?: string[] }>;
};

const SCENARIOS: Record<VerificationScenario, { query: string; extra: Record<string, unknown> }> = {
  list: { query: "show work orders", extra: {} },
  chart: { query: "show work orders as a pie chart", extra: {} },
  knowledge: { query: "search the work-order SOP", extra: {} },
  draft: {
    query: "create a synthetic work order for the demo",
    extra: { work_order_draft: { title: "Synthetic demo follow-up", priority: "medium", assignee_id: "assignee-dev-a", ledger_summary: "Created from the AgentBridge v0.1 demo" } },
  },
  routing: { query: "请查询当前租户的工单，并按状态统计数量。", extra: {} },
};

const REAL_DRAFT_QUERY = "Create a work order titled Network follow-up, priority medium, assign it to assignee-dev-a, and use the ledger summary Real model validation.";

function newThreadId(): string {
  return `verify-${crypto.randomUUID().slice(0, 8)}`;
}

export function useVerificationRun() {
  const [threadId] = useState(newThreadId);
  const [scenario, setScenarioState] = useState<VerificationScenario>("chart");
  const [mode, setMode] = useState<VerificationMode>("fake");
  const [model, setModel] = useState("default");
  const [routeQuestion, setRouteQuestionState] = useState(SCENARIOS.routing.query);
  const [verification, dispatch] = useReducer(verificationReducer, initialVerificationState);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [routeDecision, setRouteDecision] = useState<RouteDecision | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const definition = SCENARIOS[scenario];
  const query = scenario === "routing"
    ? routeQuestion
    : mode === "real" && scenario === "draft" ? REAL_DRAFT_QUERY : definition.query;
  const streamUrl = useMemo(() => `${apiBase()}/chat/stream`, []);
  const cancelUrl = useMemo(() => `${apiBase()}/chat/cancel`, []);

  function setScenario(next: VerificationScenario) {
    setRouteDecision(null);
    setScenarioState(next);
  }

  function setRouteQuestion(next: string) {
    setRouteDecision(null);
    setRouteQuestionState(next);
  }

  async function run() {
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy(true);
    setError(null);
    setRouteDecision(null);
    dispatch({ type: "start" });
    try {
      const extra = mode === "real" ? { case_mode: "real" } : { ...definition.extra, case_mode: "fake" };
      let route = "work_order_ops";
      if (scenario === "routing") {
        const routeResponse = await fetch(`${apiBase()}/console/route`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query }),
          signal: controller.signal,
        });
        if (!routeResponse.ok) throw new Error(`route HTTP ${routeResponse.status}`);
        const decision = await routeResponse.json() as RouteDecision;
        setRouteDecision(decision);
        if (!decision.route) throw new Error(decision.reason || "没有找到可用的业务插件");
        route = decision.route;
      }
      await streamChatSse(streamUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, thread_id: threadId, route, model, extra }),
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

  async function reload(runId: string) {
    const response = await fetch(`${apiBase()}/runs/${encodeURIComponent(runId)}/events`, { credentials: "include" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const events = await response.json() as unknown;
    if (!Array.isArray(events)) throw new Error("invalid run event response");
    dispatch({ type: "hydrate", events });
  }

  return { scenario, setScenario, mode, setMode, model, setModel, routeQuestion, setRouteQuestion, threadId, query, routeDecision, verification, busy, error, run, cancel, reload };
}
