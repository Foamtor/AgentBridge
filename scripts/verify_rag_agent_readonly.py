"""Credential-safe acceptance probe for the read-only RAG-Agent backend."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core" / "src"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

DEMO_TENANT = "rag-agent-demo"
PROBE_QUERY = "现代农业产业园政策支持"


def acceptance_summary(
    *, hit_count: int, citations: list[dict[str, Any]], latency_ms: int
) -> dict[str, Any]:
    return {
        "status": "ok",
        "tenant_id": DEMO_TENANT,
        "hit_count": hit_count,
        "citation_ids": [str(item.get("chunk_id") or "") for item in citations],
        "latency_ms": latency_ms,
    }


async def run() -> dict[str, Any]:
    if os.environ.get("KNOWLEDGE_BACKEND", "").strip().lower() != "rag_agent_pg":
        raise RuntimeError("KNOWLEDGE_BACKEND must be rag_agent_pg")

    from adapters.knowledge_backend import build_retriever
    from config.settings import Settings

    retriever = await build_retriever(Settings())
    started = time.perf_counter()
    try:
        hits = await retriever.similarity_search(
            PROBE_QUERY, tenant_id=DEMO_TENANT, k=5
        )
        other_hits = await retriever.similarity_search(
            PROBE_QUERY, tenant_id="other", k=5
        )
    finally:
        await retriever.close()
    if not hits:
        raise RuntimeError("demo tenant returned no knowledge citations")
    if other_hits:
        raise RuntimeError("non-demo tenant returned knowledge citations")
    return acceptance_summary(
        hit_count=len(hits),
        citations=hits,
        latency_ms=round((time.perf_counter() - started) * 1000),
    )


def main() -> int:
    try:
        summary = asyncio.run(run())
    except Exception:  # noqa: BLE001
        # A connection or provider error may contain a DSN or downstream body.
        # The acceptance probe is intentionally a redacted operator signal.
        print(json.dumps({"status": "failed"}, ensure_ascii=True))
        return 1
    print(json.dumps(summary, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
