-- R-A: knowledge schema + table for langchain_pg (filterable tenant_id column).
-- Idempotent. Requires pgvector extension (pgvector/pgvector:pg16 image).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS knowledge;

-- The P2-A reference embedding service is BAAI/bge-m3 (512 dimensions).
-- A deployed collection must use one vector dimension. Switching models for
-- an existing collection requires a re-embedding migration (P2-B), not mixed
-- dimensions in one table.
CREATE TABLE IF NOT EXISTS knowledge.kb_chunks (
    langchain_id UUID PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(512),
    tenant_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    langchain_metadata JSONB
);

CREATE INDEX IF NOT EXISTS kb_chunks_tenant_id_idx
    ON knowledge.kb_chunks (tenant_id);
