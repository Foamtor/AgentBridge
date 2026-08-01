"""Live, disposable pgvector validation for the platform RAG backend.

This is intentionally skipped outside the dedicated live-test environment.  A4
acceptance requires it to run with zero skips after ``AGENTBRIDGE_TEST_KB_DSN``
is securely injected; it never falls back to FakeRetriever.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import asyncpg
import pytest
from agentbridge_core.adapters.langchain_pg_retriever import LangchainPgRetriever

LIVE_DSN = os.environ.get("AGENTBRIDGE_TEST_KB_DSN", "").strip()
pytestmark = pytest.mark.skipif(
    not LIVE_DSN,
    reason="AGENTBRIDGE_TEST_KB_DSN is required for the dedicated pgvector live test",
)

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "apps" / "api" / "migrations" / "003_knowledge_pgvector.sql"


@pytest.mark.asyncio
async def test_langchain_pg_live_tenant_isolation() -> None:
    """Ingest and retrieve only unique, redacted rows in the dedicated test DB."""

    embed_base = os.environ["EMBED_API_BASE"].rstrip("/")
    embed_model = os.environ["EMBED_MODEL"]
    embed_dimensions = int(os.environ["EMBED_DIMENSIONS"])
    prefix = f"p2a-{uuid.uuid4().hex}"
    tenant_id = f"{prefix}-tenant"
    other_tenant = f"{prefix}-other"

    connection = await asyncpg.connect(LIVE_DSN)
    try:
        await connection.execute(MIGRATION.read_text(encoding="utf-8"))
        vector_type = await connection.fetchval(
            """
            SELECT format_type(a.atttypid, a.atttypmod)
            FROM pg_attribute a
            WHERE a.attrelid = 'knowledge.kb_chunks'::regclass
              AND a.attname = 'embedding'
              AND NOT a.attisdropped
            """
        )
        assert vector_type == f"vector({embed_dimensions})"
    finally:
        await connection.close()

    retriever = await LangchainPgRetriever.create(
        dsn=LIVE_DSN,
        embed_api_base=embed_base,
        embed_model=embed_model,
        embed_dimensions=embed_dimensions,
    )
    try:
        await retriever.ingest(
            [
                {
                    "chunk_id": f"{prefix}-chunk",
                    "doc_id": f"{prefix}-doc",
                    "text": "P2-A redacted platform knowledge validation.",
                }
            ],
            tenant_id=tenant_id,
        )
        hits = await retriever.similarity_search(
            "P2-A platform knowledge", tenant_id=tenant_id, k=3
        )
        other_hits = await retriever.similarity_search(
            "P2-A platform knowledge", tenant_id=other_tenant, k=3
        )
        assert any(hit["chunk_id"] == f"{prefix}-chunk" for hit in hits)
        assert other_hits == []
    finally:
        await retriever.close()
        cleanup = await asyncpg.connect(LIVE_DSN)
        try:
            await cleanup.execute(
                "DELETE FROM knowledge.kb_chunks WHERE doc_id LIKE $1", f"{prefix}%"
            )
        finally:
            await cleanup.close()
