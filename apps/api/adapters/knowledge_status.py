"""Knowledge backend status for GET /admin/knowledge/status (Plan6 R-B)."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from config.settings import Settings

logger = logging.getLogger(__name__)


class IngestJobSource(Protocol):
    async def list_jobs(self, *, tenant_id: str, limit: int = 20) -> list[dict[str, Any]]: ...


class KnowledgeStatusProvider:
    """Build C4 status payload from settings + retriever (+ optional ingest jobs)."""

    def __init__(
        self,
        settings: Settings,
        retriever: Any,
        *,
        ingest_jobs: IngestJobSource | None = None,
    ) -> None:
        self._settings = settings
        self._retriever = retriever
        self._ingest_jobs = ingest_jobs

    async def get_status(self, *, tenant_id: str) -> dict[str, Any]:
        backend = (self._settings.knowledge_backend or "fake").strip().lower()
        embedding = await self._embedding_status(backend)
        healthy = embedding.get("status") in {"ok", "skipped"}
        jobs: list[dict[str, Any]] = []
        if self._ingest_jobs is not None:
            jobs = await self._ingest_jobs.list_jobs(tenant_id=tenant_id)
        return {
            "backend": backend,
            "healthy": healthy,
            "embedding": embedding,
            "ingest_jobs": jobs,
        }

    async def _embedding_status(self, backend: str) -> dict[str, Any]:
        if backend == "fake":
            return {"status": "skipped", "model": self._settings.embed_model or None}
        if backend != "langchain_pg":
            return {
                "status": "fail",
                "model": self._settings.embed_model or None,
                "message": f"unsupported backend {backend!r}",
            }
        model = (self._settings.embed_model or "").strip()
        if not model:
            return {"status": "fail", "model": None, "message": "EMBED_MODEL not set"}
        embeddings = getattr(self._retriever, "_embeddings", None)
        if embeddings is None:
            return {
                "status": "degraded",
                "model": model,
                "message": "retriever has no embedding client",
            }
        embed_query = getattr(embeddings, "aembed_query", None)
        if not callable(embed_query):
            return {
                "status": "degraded",
                "model": model,
                "message": "embedding client missing aembed_query",
            }
        try:
            await embed_query("health")
            return {"status": "ok", "model": model}
        except Exception as exc:  # noqa: BLE001
            logger.warning("embedding health probe failed", exc_info=True)
            return {"status": "degraded", "model": model, "message": str(exc)}


def build_knowledge_status_provider(
    settings: Settings,
    retriever: Any,
    *,
    ingest_jobs: IngestJobSource | None = None,
) -> KnowledgeStatusProvider:
    return KnowledgeStatusProvider(
        settings,
        retriever,
        ingest_jobs=ingest_jobs,
    )
