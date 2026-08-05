import { describe, expect, it } from "vitest";
import { initialVerificationState, verificationReducer } from "./reducer";

describe("verificationReducer", () => {
  it("deduplicates and orders sequenced SSE events", () => {
    const first = { type: "text_delta", event_id: "e-2", sequence: 2 };
    const duplicate = { ...first };
    const state = verificationReducer(
      verificationReducer(initialVerificationState, { type: "start" }),
      { type: "event", event: first },
    );
    const next = verificationReducer(state, { type: "event", event: { type: "start", event_id: "e-1", sequence: 1 } });
    const final = verificationReducer(next, { type: "event", event: duplicate });
    expect(final.events.map((event) => event.event_id)).toEqual(["e-1", "e-2"]);
  });

  it("pauses at approval and reaches a stable terminal phase", () => {
    const waiting = verificationReducer(initialVerificationState, { type: "event", event: { type: "x.bridge.approval_required" } });
    expect(waiting.phase).toBe("waiting_approval");
    const complete = verificationReducer(waiting, { type: "event", event: { type: "done" } });
    expect(complete.phase).toBe("complete");
  });
});
