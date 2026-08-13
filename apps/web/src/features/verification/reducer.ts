import type { StreamEvent } from "../../lib/sseClient";
import type { VerificationAction, VerificationState } from "./types";

export const initialVerificationState: VerificationState = { events: [], phase: "idle" };

function eventKey(event: StreamEvent): string {
  return event.event_id ?? `${event.run_id ?? "run"}:${event.sequence ?? "unknown"}:${event.type}`;
}

function orderedUnique(events: StreamEvent[]): StreamEvent[] {
  const seen = new Set<string>();
  return [...events]
    .filter((event) => {
      const key = eventKey(event);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((left, right) => {
      if (left.sequence === undefined || right.sequence === undefined) return 0;
      return left.sequence - right.sequence;
    });
}

function eventPhase(type: string): VerificationState["phase"] | undefined {
  if (type === "x.bridge.approval_required") return "waiting_approval";
  if (type === "done") return "complete";
  if (type === "cancelled") return "cancelled";
  if (type === "error") return "error";
  return undefined;
}

export function verificationReducer(
  state: VerificationState,
  action: VerificationAction,
): VerificationState {
  switch (action.type) {
    case "reset": return initialVerificationState;
    case "start": return { events: [], phase: "running" };
    case "hydrate": {
      const events = orderedUnique(action.events);
      const terminal = [...events].reverse().find((event) => eventPhase(event.type));
      return { ...state, events, phase: terminal ? eventPhase(terminal.type)! : state.phase };
    }
    case "error": return { ...state, phase: "error", error: action.message };
    case "event": {
      const events = orderedUnique([...state.events, action.event]);
      const type = action.event.type;
      const phase = eventPhase(type) ?? state.phase;
      return { ...state, events, phase };
    }
  }
}
