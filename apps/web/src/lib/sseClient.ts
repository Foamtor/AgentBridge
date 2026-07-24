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

export type StreamEvent = {
  type: string;
  run_id?: string;
  event_id?: string;
  sequence?: number;
  trace_id?: string;
  timestamp?: number;
  step?: string;
  status?: string;
  data?: Record<string, unknown>;
};

/** @deprecated Prefer StreamEvent; kept for stable-type call sites. */
export type StableEvent = StreamEvent & { type: StableEventType | string };

export type SseHandlers = {
  onEvent: (event: StreamEvent) => void;
  onError?: (err: unknown) => void;
  onDone?: () => void;
};

function parseDataLine(line: string): StreamEvent | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith("data:")) return null;
  const json = trimmed.slice(trimmed.startsWith("data: ") ? 6 : 5).trim();
  if (!json || json === "[DONE]") return null;
  return JSON.parse(json) as StreamEvent;
}

export function isExtensionEvent(type: string): boolean {
  return type.startsWith("x.");
}

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
      let idx: number;
      while ((idx = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 1);
        if (!line.trim()) continue;
        try {
          const evt = parseDataLine(line);
          if (evt) handlers.onEvent(evt);
        } catch (err) {
          handlers.onError?.(err);
        }
      }
    }
    if (buffer.trim()) {
      try {
        const evt = parseDataLine(buffer);
        if (evt) handlers.onEvent(evt);
      } catch (err) {
        handlers.onError?.(err);
      }
    }
  } finally {
    handlers.onDone?.();
  }
}
