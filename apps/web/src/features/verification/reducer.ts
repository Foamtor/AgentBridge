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

export function verificationReducer(
  state: VerificationState,
  action: VerificationAction,
): VerificationState {
  switch (action.type) {
    case "reset": return initialVerificationState;
    case "start": return { events: [], phase: "running" };
    case "hydrate": return { ...state, events: orderedUnique(action.events) };
    case "error": return { ...state, phase: "error", error: action.message };
    case "event": {
      const events = orderedUnique([...state.events, action.event]);
      const type = action.event.type;
      const phase = type === "x.bridge.approval_required" ? "waiting_approval"
        : type === "done" ? "complete"
        : type === "cancelled" ? "cancelled"
        : type === "error" ? "error"
        : state.phase;
      return { ...state, events, phase };
    }
  }
}
