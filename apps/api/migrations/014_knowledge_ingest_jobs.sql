CREATE TABLE IF NOT EXISTS bridge_knowledge_ingest_jobs (
    job_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    status TEXT NOT NULL,
    doc_count INTEGER NOT NULL,
    ingested_count INTEGER NOT NULL DEFAULT 0,
    message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS bridge_knowledge_ingest_jobs_tenant_updated_idx
    ON bridge_knowledge_ingest_jobs (tenant_id, updated_at DESC, job_id DESC);
