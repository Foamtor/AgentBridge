CREATE TABLE IF NOT EXISTS bridge_audit_log (
    audit_id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource TEXT NOT NULL,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    result TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS bridge_audit_log_tenant_created_idx
    ON bridge_audit_log (tenant_id, created_at DESC, audit_id DESC);
