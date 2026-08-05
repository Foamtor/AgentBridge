import type { StreamEvent } from "../../lib/sseClient";
import type { ContractAssertion, RunDiagnostics, ToolTrace } from "./types";

const TERMINAL = new Set(["done", "error", "cancelled"]);

function assertion(key: string, passed: boolean, detail: string): ContractAssertion {
  return { key, passed, detail };
}

export function analyzeEvents(events: StreamEvent[]): RunDiagnostics {
  const ordered = [...events].sort((left, right) => (left.sequence ?? 0) - (right.sequence ?? 0));
  const ids = ordered.flatMap((event) => event.event_id ? [event.event_id] : []);
  const duplicates = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
  const sequences = ordered.flatMap((event) => typeof event.sequence === "number" ? [event.sequence] : []);
  const runIds = new Set(ordered.flatMap((event) => event.run_id ? [event.run_id] : []));
  const traceIds = new Set(ordered.flatMap((event) => event.trace_id ? [event.trace_id] : []));
  const terminal = [...ordered].reverse().find((event) => TERMINAL.has(event.type));
  const sequenceOk = sequences.length === ordered.length
    && sequences.every((value, index) => index === 0 || value > sequences[index - 1]);
  const assertions = [
    assertion("start_event", ordered[0]?.type === "start", "first event is start"),
    assertion("terminal_event", Boolean(terminal), "run contains done, error, or cancelled"),
    assertion("event_ids", ids.length === ordered.length, "every event has an event_id"),
    assertion("unique_event_ids", duplicates.length === 0, "event_id values are unique"),
    assertion("sequence", sequenceOk, "sequence values are present, ordered, and unique"),
    assertion("run_id", runIds.size === 1, "events share one run_id"),
    assertion("trace_id", traceIds.size === 1, "events share one trace_id"),
  ];
  const firstTimestamp = ordered.find((event) => typeof event.timestamp === "number")?.timestamp;
  const lastTimestamp = [...ordered].reverse().find((event) => typeof event.timestamp === "number")?.timestamp;
  const calls = new Map<string, ToolTrace>();
  const tools: ToolTrace[] = [];
  ordered.forEach((event) => {
    if (event.type !== "tool_call" && event.type !== "tool_result") return;
    const data = event.data ?? {};
    const id = String(data.tool_call_id ?? data.id ?? data.name ?? "unknown");
    if (event.type === "tool_call") {
      calls.set(id, { tool_call_id: id, name: String(data.name ?? "unknown"), args: data.args, started_at: event.timestamp });
      return;
    }
    const call = calls.get(id) ?? { tool_call_id: id, name: String(data.name ?? "unknown") };
    call.result = data;
    call.ended_at = event.timestamp;
    if (typeof call.started_at === "number" && typeof call.ended_at === "number") call.duration_ms = call.ended_at - call.started_at;
    tools.push(call);
    calls.delete(id);
  });
  tools.push(...calls.values());
  const eventTypes: Record<string, number> = {};
  ordered.forEach((event) => { eventTypes[event.type] = (eventTypes[event.type] ?? 0) + 1; });
  return {
    run_id: [...runIds][0],
    trace_id: [...traceIds][0],
    terminal: terminal?.type,
    event_count: ordered.length,
    duration_ms: typeof firstTimestamp === "number" && typeof lastTimestamp === "number" ? lastTimestamp - firstTimestamp : undefined,
    contract_ok: assertions.every((item) => item.passed),
    assertions,
    duplicate_event_ids: duplicates,
    milestones: ordered.map((event, index) => ({
      type: event.type,
      step: event.step,
      sequence: event.sequence,
      timestamp: event.timestamp,
      offset_ms: typeof event.timestamp === "number" && typeof firstTimestamp === "number" ? event.timestamp - firstTimestamp : undefined,
      gap_ms: typeof event.timestamp === "number" && typeof ordered[index + 1]?.timestamp === "number" ? (ordered[index + 1].timestamp as number) - event.timestamp : undefined,
    })),
    tools,
    event_types: eventTypes,
  };
}

export function mergeAnswer(events: StreamEvent[]): string {
  return events.filter((event) => event.type === "text_delta")
    .map((event) => String(event.data?.content ?? event.data?.text ?? ""))
    .join("");
}

export function formatDuration(value?: number): string {
  if (value === undefined) return "-";
  return value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(2)} s`;
}
