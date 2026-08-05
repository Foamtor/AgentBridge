import type { StreamEvent } from "../../lib/sseClient";

export type VerificationState = {
  events: StreamEvent[];
  phase: "idle" | "running" | "waiting_approval" | "complete" | "error" | "cancelled";
  error?: string;
};

export type VerificationAction =
  | { type: "reset" }
  | { type: "start" }
  | { type: "event"; event: StreamEvent }
  | { type: "hydrate"; events: StreamEvent[] }
  | { type: "error"; message: string };
