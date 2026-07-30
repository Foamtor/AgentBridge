-- Durable, platform-generic approval action records.

CREATE TABLE IF NOT EXISTS approval_records (
    approval_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    route TEXT,
    run_id TEXT,
    thread_id TEXT,
    storage_key TEXT,
    sequence INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    decision TEXT,
    reason TEXT,
    action JSONB,
    requester_context JSONB,
    result JSONB,
    result_delivery_error TEXT,
    error TEXT,
    execution_started_at TIMESTAMPTZ,
    execution_lease_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS approval_records_tenant_approval_idx
    ON approval_records (tenant_id, approval_id);
CREATE INDEX IF NOT EXISTS approval_records_tenant_status_idx
    ON approval_records (tenant_id, status);
