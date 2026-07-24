export type BridgeEvent = {
  type: string;
  run_id: string;
  sequence: number;
  data?: Record<string, unknown>;
  event_id?: string;
  trace_id?: string;
  timestamp?: number;
  step?: string;
  status?: string;
};

/** Parse one SSE line (`data: {...}`). Returns null for non-data / [DONE]. */
export function parseSseChunk(line: string): BridgeEvent | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith("data:")) return null;
  const json = trimmed.slice(trimmed.startsWith("data: ") ? 6 : 5).trim();
  if (!json || json === "[DONE]") return null;
  const raw = JSON.parse(json) as Record<string, unknown>;
  return {
    type: String(raw.type ?? ""),
    run_id: String(raw.run_id ?? ""),
    sequence: Number(raw.sequence ?? 0),
    data: (raw.data as Record<string, unknown> | undefined) ?? undefined,
    event_id: raw.event_id != null ? String(raw.event_id) : undefined,
    trace_id: raw.trace_id != null ? String(raw.trace_id) : undefined,
    timestamp: raw.timestamp != null ? Number(raw.timestamp) : undefined,
    step: raw.step != null ? String(raw.step) : undefined,
    status: raw.status != null ? String(raw.status) : undefined,
  };
}
