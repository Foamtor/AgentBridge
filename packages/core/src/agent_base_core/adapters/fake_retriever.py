"""In-memory Retriever with tenant namespaces (no pgvector required)."""

from __future__ import annotations

from typing import Any


class FakeRetriever:
    def __init__(self) -> None:
        self._docs: dict[str, list[dict[str, Any]]] = {}

    async def ingest(
        self, docs: list[dict[str, Any]], *, tenant_id: str
    ) -> int:
        bucket = self._docs.setdefault(tenant_id, [])
        for d in docs:
            bucket.append(dict(d))
        return len(docs)

    async def similarity_search(
        self, query: str, *, tenant_id: str, k: int = 4
    ) -> list[dict[str, Any]]:
        q = query.lower()
        scored: list[tuple[int, dict[str, Any]]] = []
        for doc in self._docs.get(tenant_id, []):
            text = str(doc.get("text") or "")
            score = sum(1 for w in q.split() if w and w in text.lower())
            if score:
                scored.append((score, dict(doc)))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:k]]
