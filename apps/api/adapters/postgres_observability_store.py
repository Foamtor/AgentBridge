"""PostgreSQL adapters for durable platform run evidence and annotations."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any


class _PostgresStore:
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

    async def close(self) -> None:
        async with self._pool_lock:
            if self._pool is not None:
                await self._pool.close()
                self._pool = None


class PostgresRunStore(_PostgresStore):
    async def upsert(self, run: dict[str, Any]) -> None:
        run_id = str(run["run_id"])
        tenant_id = str(run["tenant_id"])
        row = await self._fetchrow(
            """
            INSERT INTO bridge_runs (
                run_id, tenant_id, thread_id, route, trace_id, status,
                started_at, ended_at, projection
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
            ON CONFLICT (run_id) DO UPDATE SET
                thread_id = COALESCE(EXCLUDED.thread_id, bridge_runs.thread_id),
                route = COALESCE(EXCLUDED.route, bridge_runs.route),
                trace_id = COALESCE(EXCLUDED.trace_id, bridge_runs.trace_id),
                status = COALESCE(EXCLUDED.status, bridge_runs.status),
                started_at = COALESCE(EXCLUDED.started_at, bridge_runs.started_at),
                ended_at = COALESCE(EXCLUDED.ended_at, bridge_runs.ended_at),
                projection = bridge_runs.projection || EXCLUDED.projection,
                updated_at = NOW()
            WHERE bridge_runs.tenant_id = EXCLUDED.tenant_id
            RETURNING run_id
            """,
            run_id,
            tenant_id,
            run.get("thread_id"),
            run.get("route"),
            run.get("trace_id"),
            run.get("status"),
            _timestamp(run.get("started_at")),
            _timestamp(run.get("ended_at")),
            _json(run),
        )
        if row is None:
            raise PermissionError("cross_tenant")

    async def get(
        self, run_id: str, *, tenant_id: str
    ) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            SELECT run_id, tenant_id, thread_id, route, trace_id, status,
                   started_at, ended_at, projection
            FROM bridge_runs WHERE run_id = $1 AND tenant_id = $2
            """,
            run_id,
            tenant_id,
        )
        return _run_from_row(row) if row is not None else None

    async def list_by_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT run_id, tenant_id, thread_id, route, trace_id, status,
                       started_at, ended_at, projection
                FROM bridge_runs WHERE tenant_id = $1
                """,
                tenant_id,
            )
        return [_run_from_row(dict(row)) for row in rows]

    async def _fetchrow(self, sql: str, *params: Any) -> dict[str, Any] | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(sql, *params)
        return dict(row) if row is not None else None


class PostgresEventLog(_PostgresStore):
    async def append(
        self, run_id: str, event: dict[str, Any], *, tenant_id: str
    ) -> None:
        event_id = str(event.get("event_id") or "")
        if not event_id:
            raise ValueError("event_id is required for durable event storage")
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO bridge_run_events (
                    tenant_id, run_id, event_id, sequence, event
                ) VALUES ($1, $2, $3, $4, $5::jsonb)
                """,
                tenant_id,
                run_id,
                event_id,
                int(event.get("sequence") or 0),
                _json(event),
            )

    async def list(
        self, run_id: str, *, tenant_id: str
    ) -> list[dict[str, Any]]:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT event FROM bridge_run_events
                WHERE tenant_id = $1 AND run_id = $2
                ORDER BY sequence, event_id
                """,
                tenant_id,
                run_id,
            )
        return [_decode_json(row["event"]) for row in rows]

    async def health_check(self) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute("SELECT 1")


class PostgresMessageStore(_PostgresStore):
    async def append_message(
        self, tenant_id: str, thread_id: str, message: dict[str, Any]
    ) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO bridge_thread_messages (
                    tenant_id, thread_id, run_id, role, content, message
                ) VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                """,
                tenant_id,
                thread_id,
                message.get("run_id"),
                message.get("role"),
                message.get("content"),
                _json(message),
            )

    async def list_messages(
        self, tenant_id: str, thread_id: str
    ) -> list[dict[str, Any]]:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT message FROM bridge_thread_messages
                WHERE tenant_id = $1 AND thread_id = $2
                ORDER BY message_id
                """,
                tenant_id,
                thread_id,
            )
        return [_decode_json(row["message"]) for row in rows]


class PostgresRunAnnotationStore(_PostgresStore):
    async def create(self, annotation: dict[str, Any]) -> dict[str, Any]:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO bridge_run_annotations (
                    annotation_id, tenant_id, run_id, author_id, category,
                    rating, reason, expected_behavior, tags, annotation
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10::jsonb)
                """,
                annotation["annotation_id"],
                annotation["tenant_id"],
                annotation["run_id"],
                annotation.get("author_id"),
                annotation["category"],
                annotation["rating"],
                annotation["reason"],
                annotation.get("expected_behavior"),
                _json(annotation.get("tags") or []),
                _json(annotation),
            )
        return dict(annotation)

    async def list_for_run(
        self, tenant_id: str, run_id: str
    ) -> list[dict[str, Any]]:
        return await self._list("WHERE tenant_id = $1 AND run_id = $2", tenant_id, run_id)

    async def list_for_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        return await self._list("WHERE tenant_id = $1", tenant_id)

    async def delete(self, tenant_id: str, annotation_id: str) -> bool:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            result = await connection.execute(
                """
                DELETE FROM bridge_run_annotations
                WHERE tenant_id = $1 AND annotation_id = $2
                """,
                tenant_id,
                annotation_id,
            )
        return result.endswith(" 1")

    async def _list(self, clause: str, *params: Any) -> list[dict[str, Any]]:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                f"SELECT annotation FROM bridge_run_annotations {clause} "
                "ORDER BY created_at DESC, annotation_id DESC",
                *params,
            )
        return [_decode_json(row["annotation"]) for row in rows]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _decode_json(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return dict(json.loads(value))
    return dict(value)


def _timestamp(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise TypeError("timestamp must be an ISO 8601 string or datetime")


def _run_from_row(row: dict[str, Any]) -> dict[str, Any]:
    result = _decode_json(row.pop("projection"))
    for key, value in row.items():
        if value is not None:
            result[key] = value.isoformat() if hasattr(value, "isoformat") else value
    return result
