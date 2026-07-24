#!/usr/bin/env python3
"""Ingest sample docs into app.state.retriever (dev helper).

Usage (API process already running is not required — this seeds a FakeRetriever
for offline demos / tests):

  python scripts/ingest_demo_rag.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core" / "src"))

from agent_base_core.adapters.fake_retriever import FakeRetriever  # noqa: E402


async def main() -> None:
    r = FakeRetriever()
    n = await r.ingest(
        [
            {"id": "d1", "text": "refund policy allows 30 days", "tenant_id": "acme"},
            {"id": "d2", "text": "shipping takes 5 days", "tenant_id": "acme"},
        ],
        tenant_id="acme",
    )
    hits = await r.similarity_search("refund policy", tenant_id="acme")
    cross = await r.similarity_search("refund policy", tenant_id="other")
    print(f"ingested={n} hits={len(hits)} cross_tenant={len(cross)}")
    assert hits and not cross


if __name__ == "__main__":
    asyncio.run(main())
