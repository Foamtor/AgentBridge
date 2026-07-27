"""In-memory ingest job store for R-B status and auditing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryIngestJobStore:
    def __init__(self) -> None:
        self._jobs: list[dict[str, Any]] = []

    async def create_job(
        self,
        *,
        job_id: str,
        tenant_id: str,
        doc_count: int,
    ) -> dict[str, Any]:
        now = _utc_now_iso()
        job = {
            "job_id": job_id,
            "tenant_id": tenant_id,
            "status": "running",
            "doc_count": doc_count,
            "ingested_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        self._jobs.append(job)
        return dict(job)

    async def complete_job(
        self,
        job_id: str,
        *,
        ingested_count: int,
    ) -> dict[str, Any] | None:
        for job in self._jobs:
            if job.get("job_id") == job_id:
                job["status"] = "completed"
                job["ingested_count"] = ingested_count
                job["updated_at"] = _utc_now_iso()
                return dict(job)
        return None

    async def fail_job(self, job_id: str, *, message: str) -> None:
        for job in self._jobs:
            if job.get("job_id") == job_id:
                job["status"] = "error"
                job["message"] = message
                job["updated_at"] = _utc_now_iso()
                return

    async def list_jobs(
        self, *, tenant_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        rows = [j for j in self._jobs if j.get("tenant_id") == tenant_id]
        rows.sort(key=lambda j: str(j.get("updated_at") or ""), reverse=True)
        out: list[dict[str, Any]] = []
        for job in rows[:limit]:
            out.append(
                {
                    "job_id": job.get("job_id"),
                    "status": job.get("status"),
                    "updated_at": job.get("updated_at"),
                    "ingested_count": job.get("ingested_count", 0),
                }
            )
        return out
