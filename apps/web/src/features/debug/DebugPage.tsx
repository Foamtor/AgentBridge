import { useMemo, useRef, useState } from "react";
import { apiBase } from "../../lib/apiBase";
import { streamChatSse, type StableEvent } from "../../lib/sseClient";
import { getToken, setToken } from "../auth/token";
import { EventTimeline } from "./EventTimeline";
import { SendPanel } from "./SendPanel";
import { SessionBar } from "./SessionBar";

function newThreadId(): string {
  return `t-${crypto.randomUUID().slice(0, 8)}`;
}

export function DebugPage() {
  const [threadId, setThreadId] = useState(newThreadId);
  const [route, setRoute] = useState("echo");
  const [token, setTokenState] = useState(getToken);
  const [query, setQuery] = useState("hello");
  const [events, setEvents] = useState<StableEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const streamUrl = useMemo(() => `${apiBase()}/chat/stream`, []);
  const cancelUrl = useMemo(() => `${apiBase()}/chat/cancel`, []);

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
          body: JSON.stringify({ query, thread_id: tid, route }),
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
        <h1>Agent-Base 调试台</h1>
        <p className="lede">发送到 /chat/stream，观察稳定 SSE 事件时间线。</p>
      </header>
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
      {error ? <p className="error">{error}</p> : null}
      <EventTimeline events={events} />
    </main>
  );
}
