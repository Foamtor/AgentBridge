"""KnowledgeIngest stub for backends without HTTP ingest support."""

from __future__ import annotations

from typing import Any


class UnsupportedKnowledgeIngest:
    def __init__(self, backend: str) -> None:
        self._backend = backend

    def supports_ingest(self) -> bool:
        return False

    async def ingest_documents(
        self,
        docs: list[dict[str, Any]],
        *,
        tenant_id: str,
    ) -> dict[str, Any]:
        raise NotImplementedError(f"ingest unsupported for backend {self._backend!r}")
