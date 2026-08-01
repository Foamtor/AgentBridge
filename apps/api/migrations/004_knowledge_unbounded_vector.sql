-- Migrate pre-P2-A installations whose 003 migration fixed vectors at 1024.
-- No data is deleted; a typmod-less vector column accepts each configured
-- embedding model's native dimension.  Run after 003_knowledge_pgvector.sql.

ALTER TABLE IF EXISTS knowledge.kb_chunks
    ALTER COLUMN embedding TYPE vector USING embedding::vector;
