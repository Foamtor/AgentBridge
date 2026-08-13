"""PostgreSQL-backed knowledge ingest job status store."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any


class PostgresIngestJobStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: Any | None = None
        self._pool_lock = asyncio.Lock()

    async def _ensure_pool(self) -> Any:
        if self._pool is not None:
            return self._pool
        async with self._pool_lock:
            if self._pool is None:
                import asyncpg

                self._pool = await asyncpg.create_pool(
                    dsn=self._dsn, min_size=1, max_size=5
                )
        return self._pool

    async def setup(self) -> None:
        migration = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "014_knowledge_ingest_jobs.sql"
        )
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(migration.read_text(encoding="utf-8"))

    async def create_job(
        self,
        *,
        job_id: str,
        tenant_id: str,
        doc_count: int,
    ) -> dict[str, Any]:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                INSERT INTO bridge_knowledge_ingest_jobs
                    (job_id, tenant_id, status, doc_count, ingested_count)
                VALUES ($1, $2, 'running', $3, 0)
                RETURNING job_id, tenant_id, status, doc_count, ingested_count,
                          message, created_at, updated_at
                """,
                job_id,
                tenant_id,
                int(doc_count),
            )
        return _job_from_row(row)

    async def complete_job(
        self,
        job_id: str,
        *,
        ingested_count: int,
    ) -> dict[str, Any] | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                UPDATE bridge_knowledge_ingest_jobs
                SET status = 'completed', ingested_count = $2, updated_at = NOW()
                WHERE job_id = $1
                RETURNING job_id, tenant_id, status, doc_count, ingested_count,
                          message, created_at, updated_at
                """,
                job_id,
                int(ingested_count),
            )
        return _job_from_row(row) if row is not None else None

    async def fail_job(self, job_id: str, *, message: str) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                UPDATE bridge_knowledge_ingest_jobs
                SET status = 'error', message = $2, updated_at = NOW()
                WHERE job_id = $1
                """,
                job_id,
                str(message)[:1000],
            )

    async def list_jobs(
        self, *, tenant_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT job_id, tenant_id, status, doc_count, ingested_count,
                       message, created_at, updated_at
                FROM bridge_knowledge_ingest_jobs
                WHERE tenant_id = $1
                ORDER BY updated_at DESC, job_id DESC
                LIMIT $2
                """,
                tenant_id,
                max(1, min(int(limit), 100)),
            )
        return [
            {
                "job_id": row["job_id"],
                "status": row["status"],
                "updated_at": _iso(row["updated_at"]),
                "ingested_count": int(row["ingested_count"] or 0),
            }
            for row in rows
        ]

    async def close(self) -> None:
        async with self._pool_lock:
            if self._pool is not None:
                await self._pool.close()
                self._pool = None


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _job_from_row(row: Any) -> dict[str, Any]:
    return {
        "job_id": row["job_id"],
        "tenant_id": row["tenant_id"],
        "status": row["status"],
        "doc_count": int(row["doc_count"] or 0),
        "ingested_count": int(row["ingested_count"] or 0),
        "message": row["message"],
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }
