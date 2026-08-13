"""PostgreSQL-backed audit logger for production evidence retention."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


class PostgresAuditLogger:
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
            Path(__file__).resolve().parents[1] / "migrations" / "015_audit_log.sql"
        )
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(migration.read_text(encoding="utf-8"))

    async def log(
        self,
        *,
        user_id: str,
        tenant_id: str,
        action: str,
        resource: str,
        detail: dict[str, Any],
        result: str,
    ) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO bridge_audit_log
                    (tenant_id, user_id, action, resource, detail, result)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6)
                """,
                tenant_id,
                user_id,
                action,
                resource,
                json.dumps(detail, ensure_ascii=False, default=str),
                result,
            )

    async def list_records(
        self, *, tenant_id: str, limit: int = 10000
    ) -> list[dict[str, Any]]:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT user_id, tenant_id, action, resource, detail, result
                FROM bridge_audit_log
                WHERE tenant_id = $1
                ORDER BY created_at ASC, audit_id ASC
                LIMIT $2
                """,
                tenant_id,
                max(1, min(int(limit), 100000)),
            )
        return [_record_from_row(row) for row in rows]

    async def close(self) -> None:
        async with self._pool_lock:
            if self._pool is not None:
                await self._pool.close()
                self._pool = None


def _record_from_row(row: Any) -> dict[str, Any]:
    detail = row["detail"]
    if isinstance(detail, str):
        detail = json.loads(detail)
    return {
        "user_id": row["user_id"],
        "tenant_id": row["tenant_id"],
        "action": row["action"],
        "resource": row["resource"],
        "detail": dict(detail or {}),
        "result": row["result"],
    }
