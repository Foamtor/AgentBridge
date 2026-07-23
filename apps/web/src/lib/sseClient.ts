export type StableEventType =
  | "start"
  | "step_update"
  | "text_delta"
  | "tool_call"
  | "tool_result"
  | "done"
  | "error"
  | "cancel_requested"
  | "cancelled";

export type StableEvent = {
  type: StableEventType | string;
  run_id?: string;
  event_id?: string;
  sequence?: number;
  trace_id?: string;
  timestamp?: number;
  step?: string;
  status?: string;
  data?: Record<string, unknown>;
};

export type SseHandlers = {
  onEvent: (event: StableEvent) => void;
  onError?: (err: unknown) => void;
  onDone?: () => void;
};

/** Parse SSE `data: JSON` lines from a fetch body stream. */
export async function streamChatSse(
  url: string,
  init: RequestInit,
  handlers: SseHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(url, { ...init, signal });
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      detail = await res.json();
    } catch {
      /* ignore */
    }
    throw Object.assign(new Error(`HTTP ${res.status}`), { status: res.status, detail });
  }
  if (!res.body) {
    handlers.onDone?.();
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data: ")) continue;
        const json = line.slice("data: ".length);
        try {
          handlers.onEvent(JSON.parse(json) as StableEvent);
        } catch (err) {
          handlers.onError?.(err);
        }
      }
    }
  } finally {
    handlers.onDone?.();
  }
}
