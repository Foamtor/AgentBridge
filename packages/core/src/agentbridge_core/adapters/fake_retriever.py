"""In-memory Retriever with tenant namespaces (no pgvector required)."""

from __future__ import annotations

from typing import Any

from agentbridge_core.protocol.knowledge import (
    KnowledgeHit,
    doc_to_knowledge_hit,
    normalize_ingest_doc,
    require_tenant_id,
)


class FakeRetriever:
    def __init__(self) -> None:
        self._docs: dict[str, list[dict[str, Any]]] = {}

    async def ingest(
        self, docs: list[dict[str, Any]], *, tenant_id: str
    ) -> int:
        tid = require_tenant_id(tenant_id)
        normalized = [normalize_ingest_doc(d, tenant_id=tid) for d in docs]
        bucket = self._docs.setdefault(tid, [])
        for d in normalized:
            bucket.append(d)
        return len(normalized)

    async def similarity_search(
        self, query: str, *, tenant_id: str, k: int = 5
    ) -> list[KnowledgeHit]:
        tid = require_tenant_id(tenant_id)
        q = query.lower()
        scored: list[tuple[int, dict[str, Any]]] = []
        for doc in self._docs.get(tid, []):
            text = str(doc.get("text") or "")
            score = sum(1 for w in q.split() if w and w in text.lower())
            if score:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[KnowledgeHit] = []
        for score, doc in scored[:k]:
            hit = doc_to_knowledge_hit(doc, tenant_id=tid, score=float(score))
            if hit["tenant_id"] != tid:
                continue
            out.append(hit)
        return out
