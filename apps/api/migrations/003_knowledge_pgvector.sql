-- R-A: knowledge schema + table for langchain_pg (filterable tenant_id column).
-- Idempotent. Requires pgvector extension (pgvector/pgvector:pg16 image).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS knowledge;

-- embedding vector size must match EMBED_DIMENSIONS at runtime; default 1024.
-- If your TEI model uses another size, edit vector(N) before first apply.
CREATE TABLE IF NOT EXISTS knowledge.kb_chunks (
    langchain_id UUID PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1024),
    tenant_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    langchain_metadata JSONB
);

CREATE INDEX IF NOT EXISTS kb_chunks_tenant_id_idx
    ON knowledge.kb_chunks (tenant_id);
