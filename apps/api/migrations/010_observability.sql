-- Durable platform evidence for Plugin Playground. All access is tenant-scoped.
CREATE TABLE IF NOT EXISTS bridge_runs (
    run_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    thread_id TEXT,
    route TEXT,
    trace_id TEXT,
    status TEXT,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    projection JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS bridge_runs_tenant_started_idx
    ON bridge_runs (tenant_id, started_at DESC, run_id DESC);
CREATE INDEX IF NOT EXISTS bridge_runs_tenant_thread_idx
    ON bridge_runs (tenant_id, thread_id, started_at DESC);

CREATE TABLE IF NOT EXISTS bridge_run_events (
    tenant_id TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES bridge_runs(run_id) ON DELETE CASCADE,
    event_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, run_id, event_id)
);
CREATE INDEX IF NOT EXISTS bridge_run_events_replay_idx
    ON bridge_run_events (tenant_id, run_id, sequence, event_id);

CREATE TABLE IF NOT EXISTS bridge_thread_messages (
    message_id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    run_id TEXT,
    role TEXT,
    content TEXT,
    message JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS bridge_thread_messages_lookup_idx
    ON bridge_thread_messages (tenant_id, thread_id, message_id);

CREATE TABLE IF NOT EXISTS bridge_run_annotations (
    annotation_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES bridge_runs(run_id) ON DELETE CASCADE,
    author_id TEXT,
    category TEXT NOT NULL CHECK (category IN ('note', 'badcase')),
    rating TEXT NOT NULL CHECK (rating IN ('positive', 'negative', 'neutral')),
    reason TEXT NOT NULL,
    expected_behavior TEXT NOT NULL DEFAULT '',
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    annotation JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS bridge_run_annotations_lookup_idx
    ON bridge_run_annotations (tenant_id, run_id, created_at DESC);
