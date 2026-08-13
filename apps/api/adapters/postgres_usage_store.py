"""PostgreSQL-backed token usage aggregation."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any


class PostgresUsageStore:
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
            Path(__file__).resolve().parents[1] / "migrations" / "016_token_usage.sql"
        )
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(migration.read_text(encoding="utf-8"))

    async def record(
        self,
        *,
        tenant_id: str,
        route: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        run_id: str | None = None,
        event_id: str | None = None,
        recorded_at: str | None = None,
    ) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO bridge_token_usage
                    (tenant_id, route, model, input_tokens, output_tokens, run_id, event_id, recorded_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, COALESCE($8::timestamptz, NOW()))
                """,
                tenant_id,
                route,
                model,
                int(input_tokens),
                int(output_tokens),
                run_id,
                event_id,
                _timestamp(recorded_at),
            )

    async def aggregate(
        self,
        *,
        group_by: str,
        since: str | None = None,
        until: str | None = None,
        tenant_id: str,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT tenant_id, route, model,
                       CASE WHEN $4::text IS NULL THEN NULL ELSE run_id END AS run_id,
                       SUM(input_tokens)::BIGINT AS input_tokens,
                       SUM(output_tokens)::BIGINT AS output_tokens
                FROM bridge_token_usage
                WHERE tenant_id = $1
                  AND ($2::timestamptz IS NULL OR recorded_at >= $2::timestamptz)
                  AND ($3::timestamptz IS NULL OR recorded_at <= $3::timestamptz)
                  AND ($4::text IS NULL OR run_id = $4::text)
                GROUP BY tenant_id, route, model,
                         CASE WHEN $4::text IS NULL THEN NULL ELSE run_id END
                ORDER BY tenant_id, route, model
                """,
                tenant_id,
                _timestamp(since),
                _timestamp(until),
                run_id,
            )
        buckets = [
            {
                "tenant_id": row["tenant_id"],
                "route": row["route"],
                "model": row["model"],
                "run_id": row["run_id"],
                "input_tokens": int(row["input_tokens"] or 0),
                "output_tokens": int(row["output_tokens"] or 0),
            }
            for row in rows
        ]
        total_in = sum(item["input_tokens"] for item in buckets)
        total_out = sum(item["output_tokens"] for item in buckets)
        if group_by == "tenant":
            items = _merge(buckets, "tenant_id")
            items = [
                {
                    "tenant_id": item["tenant_id"],
                    "input_tokens": item["input_tokens"],
                    "output_tokens": item["output_tokens"],
                }
                for item in items
            ]
        elif group_by == "model":
            items = _merge(buckets, "model")
            items = [
                {
                    "model": item["model"],
                    "input_tokens": item["input_tokens"],
                    "output_tokens": item["output_tokens"],
                }
                for item in items
            ]
        else:
            items = buckets
        if run_id is None:
            for item in items:
                item.pop("run_id", None)
        return {
            "window": {"since": since, "until": until},
            "group_by": group_by,
            "items": items,
            "totals": {"input_tokens": total_in, "output_tokens": total_out},
        }

    async def close(self) -> None:
        async with self._pool_lock:
            if self._pool is not None:
                await self._pool.close()
                self._pool = None


def _timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _merge(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in items:
        name = str(item[key])
        bucket = merged.setdefault(
            name,
            {key: name, "input_tokens": 0, "output_tokens": 0},
        )
        bucket["input_tokens"] += item["input_tokens"]
        bucket["output_tokens"] += item["output_tokens"]
    return list(merged.values())
