import type { StreamEvent } from "../../lib/sseClient";

export type ChatRequest = {
  query: string;
  thread_id: string;
  route: string;
  model: string;
  extra: Record<string, unknown>;
};

export type RunRecord = {
  run_id: string;
  thread_id: string;
  route: string;
  trace_id?: string;
  status: string;
  started_at?: string;
  ended_at?: string;
  request?: ChatRequest;
};

export type ThreadMessage = {
  role: "user" | "assistant" | string;
  content: string;
  run_id?: string;
  tool_trace?: Array<{ type: string; data: Record<string, unknown> }>;
};

export type ContractAssertion = { key: string; passed: boolean; detail: string };

export type Milestone = {
  type: string;
  step?: string;
  sequence?: number;
  timestamp?: number;
  offset_ms?: number;
  gap_ms?: number;
};

export type ToolTrace = {
  tool_call_id: string;
  name?: string;
  args?: unknown;
  result?: unknown;
  started_at?: number;
  ended_at?: number;
  duration_ms?: number;
};

export type RunDiagnostics = {
  run_id?: string;
  trace_id?: string;
  terminal?: string;
  event_count: number;
  duration_ms?: number;
  contract_ok: boolean;
  assertions: ContractAssertion[];
  duplicate_event_ids: string[];
  milestones: Milestone[];
  tools: ToolTrace[];
  event_types: Record<string, number>;
};

export type RunAnnotation = {
  annotation_id: string;
  run_id: string;
  category: "note" | "badcase";
  rating: "positive" | "negative" | "neutral";
  reason: string;
  expected_behavior: string;
  tags: string[];
  author_id?: string;
  created_at: string;
};

export type DiagnosticSummary = {
  total_runs: number;
  contract_failures: number;
  annotations: number;
  badcases: number;
  by_route: Record<string, { runs: number; failures: number }>;
  tool_usage: Record<string, number>;
};

export type InspectorTab = "overview" | "timing" | "tools" | "contract" | "raw" | "notes";

export type SelectedRunData = {
  run: RunRecord | null;
  events: StreamEvent[];
  messages: ThreadMessage[];
  diagnostics: RunDiagnostics | null;
  annotations: RunAnnotation[];
};
