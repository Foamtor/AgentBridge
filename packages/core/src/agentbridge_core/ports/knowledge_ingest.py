"""KnowledgeIngest protocol — document ingest with job tracking (R-B)."""

from __future__ import annotations

from typing import Any, Protocol


class KnowledgeIngest(Protocol):
    def supports_ingest(self) -> bool: ...

    async def ingest_documents(
        self,
        docs: list[dict[str, Any]],
        *,
        tenant_id: str,
    ) -> dict[str, Any]: ...
