import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiBase } from "../../lib/apiBase";
import { streamChatSse, type StreamEvent } from "../../lib/sseClient";
import { getToken, setToken } from "../auth/token";
import { PlatformEvidence } from "../verification/PlatformEvidence";
import { BusinessResults } from "../verification/BusinessResults";
import { SendPanel } from "./SendPanel";
import { SessionBar } from "./SessionBar";
import { useI18n } from "../../i18n";
import { initialVerificationState, verificationReducer } from "../verification/reducer";

function newThreadId(): string {
  return `t-${crypto.randomUUID().slice(0, 8)}`;
}

export function DebugPage({ workbench = false }: { workbench?: boolean }) {
  const [searchParams] = useSearchParams();
  const { t } = useI18n();
  const [threadId, setThreadId] = useState(newThreadId);
  const [route, setRoute] = useState(workbench ? "work_order_ops" : "echo");
  const [token, setTokenState] = useState(getToken);
  const [query, setQuery] = useState(workbench ? "show work orders as a pie chart" : "hello");
  const [verification, dispatchVerification] = useReducer(verificationReducer, initialVerificationState);
  const [extra, setExtra] = useState<Record<string, unknown>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const streamUrl = useMemo(() => `${apiBase()}/chat/stream`, []);
  const cancelUrl = useMemo(() => `${apiBase()}/chat/cancel`, []);
  const replayRunId = searchParams.get("run_id");

  useEffect(() => {
    if (!replayRunId) return;
    const headers: Record<string, string> = {};
    if (token.trim()) headers.Authorization = `Bearer ${token.trim()}`;
    void fetch(`${apiBase()}/runs/${encodeURIComponent(replayRunId)}/events`, { headers })
      .then(async (response) => {
        if (!response.ok) throw new Error(`replay failed HTTP ${response.status}`);
        const replay = (await response.json()) as StreamEvent[];
        dispatchVerification({ type: "hydrate", events: replay });
      })
      .catch((err) => setError(String(err)));
  }, [replayRunId, token]);

  function updateToken(v: string) {
    setTokenState(v);
    setToken(v);
  }

  async function sendOnce(tid: string): Promise<void> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (token.trim()) headers.Authorization = `Bearer ${token.trim()}`;

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setBusy(true);
    setError(null);
    dispatchVerification({ type: "start" });

    try {
      await streamChatSse(
        streamUrl,
        {
          method: "POST",
          headers,
          body: JSON.stringify({ query, thread_id: tid, route, extra }),
        },
        {
          onEvent: (e) => dispatchVerification({ type: "event", event: e }),
          onError: (err) => setError(String(err)),
        },
        ctrl.signal,
      );
    } catch (err) {
      const e = err as { status?: number; detail?: unknown; message?: string };
      if (e.status === 409) {
        setError("409 thread_busy");
      } else {
        setError(e.message ?? String(err));
      }
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  }

  async function onSend() {
    await sendOnce(threadId);
  }

  function applyGoldenPreset(preset: "list" | "chart" | "draft") {
    setRoute("work_order_ops");
    if (preset === "list") {
      setQuery("show work orders");
      setExtra({});
    } else if (preset === "chart") {
      setQuery("show work orders as a pie chart");
      setExtra({});
    } else {
      setQuery("create a synthetic work order for the demo");
      setExtra({ work_order_draft: { title: "Synthetic demo follow-up", priority: "medium", assignee_id: "assignee-dev-a", ledger_summary: "Created from the AgentBridge v0.1 demo" } });
    }
  }

  async function onCancel() {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (token.trim()) headers.Authorization = `Bearer ${token.trim()}`;
    try {
      const res = await fetch(cancelUrl, {
        method: "POST",
        headers,
        body: JSON.stringify({ thread_id: threadId }),
      });
      if (!res.ok && res.status !== 404) {
        setError(`cancel failed HTTP ${res.status}`);
      }
    } catch (err) {
      setError(String(err));
    } finally {
      abortRef.current?.abort();
    }
  }

  async function onDoubleFire() {
    setError(null);
    const tid = threadId;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (token.trim()) headers.Authorization = `Bearer ${token.trim()}`;
    const body = JSON.stringify({ query, thread_id: tid, route });
    // First request holds the lock; second should 409. Independent of timeline state.
    const first = fetch(streamUrl, { method: "POST", headers, body });
    await new Promise((r) => setTimeout(r, 40));
    try {
      const res = await fetch(streamUrl, { method: "POST", headers, body });
      if (res.status === 409) {
        setError("409 thread_busy（连点成功）");
      } else {
        setError(`连点结果 HTTP ${res.status}`);
      }
    } catch (err) {
      setError(String(err));
    } finally {
      try {
        await fetch(cancelUrl, {
          method: "POST",
          headers,
          body: JSON.stringify({ thread_id: tid }),
        });
      } catch {
        /* ignore */
      }
      void first;
    }
  }

  const advancedMode = searchParams.get("mode") === "advanced";

  return (
    <main className={`page ${workbench ? "verification-workbench" : "advanced-debug"}`}>
      <header>
        <p className="eyebrow">{t("product")} / {t("preview")}</p>
        <h1>{workbench ? t("verifyTitle") : t("advancedTitle")}</h1>
        <p className="lede">{workbench ? t("verifyDescription") : t("advancedDescription")}</p>
      </header>
      {replayRunId ? <p className="muted">回放 run：{replayRunId}</p> : null}
      {workbench ? <div className="context-strip"><span>{t("route")}</span><code>work_order_ops</code><span>{t("data")}</span><strong>synthetic_redacted</strong><span>{t("tenant")}</span><code>dev</code></div> : <SessionBar threadId={threadId} route={route} token={token} onThreadId={setThreadId} onRoute={setRoute} onToken={updateToken} />}
      {workbench ? <div className="scenario-hint"><strong>{t("chooseScenario")}</strong><span>{t("scenarioHint")}</span></div> : null}
      <SendPanel
        query={query}
        busy={busy}
        onQuery={setQuery}
        onSend={() => void onSend()}
        onCancel={() => void onCancel()}
        onDoubleFire={() => void onDoubleFire()}
      />
      <BusinessResults events={verification.events} token={token} onPreset={applyGoldenPreset} />
      {error ? <p className="error">{error}</p> : null}
      <details className="technical-evidence" open={!workbench || advancedMode}><summary>{t("technicalEvidence")}</summary><PlatformEvidence events={verification.events} /></details>
    </main>
  );
}
