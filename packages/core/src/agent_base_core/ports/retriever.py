"""Retriever protocol — tenant-scoped similarity search."""

from __future__ import annotations

from typing import Any, Protocol


class Retriever(Protocol):
    async def similarity_search(
        self,
        query: str,
        *,
        tenant_id: str,
        k: int = 4,
    ) -> list[dict[str, Any]]: ...

    async def ingest(
        self,
        docs: list[dict[str, Any]],
        *,
        tenant_id: str,
    ) -> int: ...
