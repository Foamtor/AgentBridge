-- Hot-reloadable platform parameters only. Deployment and secret settings remain outside this table.
CREATE TABLE IF NOT EXISTS bridge_runtime_config (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_by TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT bridge_runtime_config_key_format
        CHECK (key ~ '^[A-Z][A-Z0-9_]{1,127}$')
);

CREATE TABLE IF NOT EXISTS bridge_runtime_config_audit (
    id BIGSERIAL PRIMARY KEY,
    key TEXT NOT NULL,
    value JSONB NOT NULL,
    updated_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS bridge_runtime_config_audit_key_created_idx
    ON bridge_runtime_config_audit (key, created_at DESC);
