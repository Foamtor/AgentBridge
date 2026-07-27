"""KnowledgeIngest adapter delegating to Retriever.ingest."""

from __future__ import annotations

import uuid
from typing import Any

from agentbridge_core.adapters.memory_ingest_job_store import MemoryIngestJobStore


class RetrieverKnowledgeIngest:
    def __init__(self, retriever: Any, job_store: MemoryIngestJobStore) -> None:
        self._retriever = retriever
        self._job_store = job_store

    def supports_ingest(self) -> bool:
        return True

    async def ingest_documents(
        self,
        docs: list[dict[str, Any]],
        *,
        tenant_id: str,
    ) -> dict[str, Any]:
        job_id = f"ing-{uuid.uuid4().hex[:12]}"
        await self._job_store.create_job(
            job_id=job_id,
            tenant_id=tenant_id,
            doc_count=len(docs),
        )
        try:
            ingested = await self._retriever.ingest(docs, tenant_id=tenant_id)
        except Exception as exc:
            await self._job_store.fail_job(job_id, message=str(exc))
            raise
        job = await self._job_store.complete_job(job_id, ingested_count=ingested)
        return {
            "job_id": job_id,
            "status": "completed",
            "ingested_count": ingested,
            "updated_at": job.get("updated_at") if job else None,
        }
