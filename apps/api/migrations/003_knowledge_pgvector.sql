-- R-A: knowledge schema + table for langchain_pg (filterable tenant_id column).
-- Idempotent. Requires pgvector extension (pgvector/pgvector:pg16 image).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS knowledge;

-- Keep this column dimension-agnostic.  EMBED_DIMENSIONS is validated by the
-- configured embedding provider and pgvector accepts the provider's vector;
-- this lets a deployment use its chosen compatible model without editing DDL.
CREATE TABLE IF NOT EXISTS knowledge.kb_chunks (
    langchain_id UUID PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector,
    tenant_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    langchain_metadata JSONB
);

CREATE INDEX IF NOT EXISTS kb_chunks_tenant_id_idx
    ON knowledge.kb_chunks (tenant_id);
