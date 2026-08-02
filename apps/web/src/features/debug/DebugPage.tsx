import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiBase } from "../../lib/apiBase";
import { streamChatSse, type StreamEvent } from "../../lib/sseClient";
import { getToken, setToken } from "../auth/token";
import { EventTimeline } from "./EventTimeline";
import { GoldenCasePanel } from "./GoldenCasePanel";
import { SendPanel } from "./SendPanel";
import { SessionBar } from "./SessionBar";

function newThreadId(): string {
  return `t-${crypto.randomUUID().slice(0, 8)}`;
}

export function DebugPage() {
  const [searchParams] = useSearchParams();
  const [threadId, setThreadId] = useState(newThreadId);
  const [route, setRoute] = useState("echo");
  const [token, setTokenState] = useState(getToken);
  const [query, setQuery] = useState("hello");
  const [events, setEvents] = useState<StreamEvent[]>([]);
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
        setEvents(replay);
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
    setEvents([]);

    try {
      await streamChatSse(
        streamUrl,
        {
          method: "POST",
          headers,
          body: JSON.stringify({ query, thread_id: tid, route, extra }),
        },
        {
          onEvent: (e) => setEvents((prev) => [...prev, e]),
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

  return (
    <main className="page">
      <header>
        <h1>AgentBridge 调试台</h1>
        <p className="lede">
          发送到 /chat/stream。黄金案例展示结构化 x.* 事件；未知扩展事件仍在时间线中折叠。
        </p>
      </header>
      {replayRunId ? <p className="muted">回放 run：{replayRunId}</p> : null}
      <SessionBar
        threadId={threadId}
        route={route}
        token={token}
        onThreadId={setThreadId}
        onRoute={setRoute}
        onToken={updateToken}
      />
      <SendPanel
        query={query}
        busy={busy}
        onQuery={setQuery}
        onSend={() => void onSend()}
        onCancel={() => void onCancel()}
        onDoubleFire={() => void onDoubleFire()}
      />
      <GoldenCasePanel events={events} token={token} onPreset={applyGoldenPreset} />
      {error ? <p className="error">{error}</p> : null}
      <EventTimeline events={events} />
    </main>
  );
}
