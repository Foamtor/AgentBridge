CREATE TABLE IF NOT EXISTS bridge_token_usage (
    usage_id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    route TEXT NOT NULL,
    model TEXT NOT NULL,
    run_id TEXT,
    event_id TEXT,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS bridge_token_usage_tenant_recorded_idx
    ON bridge_token_usage (tenant_id, recorded_at DESC);

ALTER TABLE bridge_token_usage ADD COLUMN IF NOT EXISTS run_id TEXT;
ALTER TABLE bridge_token_usage ADD COLUMN IF NOT EXISTS event_id TEXT;
CREATE INDEX IF NOT EXISTS bridge_token_usage_run_idx
    ON bridge_token_usage (tenant_id, run_id, recorded_at DESC);
