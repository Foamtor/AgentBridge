import { parseSseChunk, type BridgeEvent } from "./sse.js";

export type StreamHandlers = {
  onEvent: (e: BridgeEvent) => void;
  onError?: (err: unknown) => void;
};

export class AgentBridgeClient {
  constructor(
    private readonly baseUrl: string,
    private readonly opts: { getToken?: () => string | null } = {},
  ) {}

  /** Start SSE chat; returns AbortController to cancel fetch. */
  streamChat(
    body: unknown,
    handlers: StreamHandlers,
  ): AbortController {
    const ac = new AbortController();
    void this._stream(body, handlers, ac.signal);
    return ac;
  }

  async resolveApproval(
    id: string,
    decision: "allow" | "deny",
  ): Promise<void> {
    const mapped = decision === "allow" ? "approve" : "deny";
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    const token = this.opts.getToken?.();
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(`${this.baseUrl}/approvals/${id}`, {
      method: "POST",
      headers,
      body: JSON.stringify({ decision: mapped }),
    });
    if (!res.ok) {
      throw Object.assign(new Error(`HTTP ${res.status}`), {
        status: res.status,
        body: await res.text(),
      });
    }
  }

  private async _stream(
    body: unknown,
    handlers: StreamHandlers,
    signal: AbortSignal,
  ): Promise<void> {
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      };
      const token = this.opts.getToken?.();
      if (token) headers.Authorization = `Bearer ${token}`;
      const res = await fetch(`${this.baseUrl}/chat/stream`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        signal,
      });
      if (!res.ok || !res.body) {
        throw Object.assign(new Error(`HTTP ${res.status}`), {
          status: res.status,
        });
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
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
            const evt = parseSseChunk(line);
            if (evt) handlers.onEvent(evt);
          } catch (err) {
            handlers.onError?.(err);
          }
        }
      }
    } catch (err) {
      if ((err as { name?: string }).name === "AbortError") return;
      handlers.onError?.(err);
    }
  }
}

export { parseSseChunk };
export type { BridgeEvent };
