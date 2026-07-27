"""Retriever protocol — tenant-scoped similarity search."""

from __future__ import annotations

from typing import Any, Protocol

from agentbridge_core.protocol.knowledge import KnowledgeHit


class Retriever(Protocol):
    async def similarity_search(
        self,
        query: str,
        *,
        tenant_id: str,
        k: int = 5,
    ) -> list[KnowledgeHit]: ...

    async def ingest(
        self,
        docs: list[dict[str, Any]],
        *,
        tenant_id: str,
    ) -> int: ...
