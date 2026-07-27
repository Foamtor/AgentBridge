#!/usr/bin/env python3
"""Seed demo knowledge docs via Retriever.ingest (R-A; no HTTP /ingest).

Fake (default, offline):
  python scripts/ingest_demo_rag.py

langchain_pg (needs TEI + pgvector + rag extra + .env):
  set KNOWLEDGE_BACKEND=langchain_pg and EMBED_* / PG_DSN (or KB_DSN)
  python scripts/ingest_demo_rag.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core" / "src"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

DOCS = [
    {
        "chunk_id": "d1",
        "doc_id": "doc-refund",
        "text": "refund policy allows 30 days",
    },
    {
        "chunk_id": "d2",
        "doc_id": "doc-ship",
        "text": "shipping takes 5 days",
    },
]


async def _build_retriever():
    backend = (os.environ.get("KNOWLEDGE_BACKEND") or "fake").strip().lower()
    if backend == "fake":
        from agentbridge_core.adapters.fake_retriever import FakeRetriever

        return FakeRetriever(), True
    if backend == "langchain_pg":
        from adapters.knowledge_backend import build_retriever
        from config.settings import get_settings

        return await build_retriever(get_settings()), False
    raise SystemExit(f"unsupported KNOWLEDGE_BACKEND={backend!r}")


async def main() -> None:
    r, is_fake = await _build_retriever()
    try:
        n = await r.ingest(DOCS, tenant_id="acme")
        hits = await r.similarity_search("refund policy", tenant_id="acme", k=5)
        cross = await r.similarity_search("refund policy", tenant_id="other", k=5)
        print(
            f"backend={'fake' if is_fake else 'langchain_pg'} "
            f"ingested={n} hits={len(hits)} cross_tenant={len(cross)}"
        )
        assert hits and hits[0]["chunk_id"] == "d1"
        assert not cross
    finally:
        close = getattr(r, "close", None)
        if close is not None:
            result = close()
            if hasattr(result, "__await__"):
                await result


if __name__ == "__main__":
    asyncio.run(main())
