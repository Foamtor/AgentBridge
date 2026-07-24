"""Postgres DataSource via asyncpg (api host adapter)."""

from __future__ import annotations

from typing import Any


class PostgresDataSource:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: Any | None = None

    async def _ensure_pool(self) -> Any:
        if self._pool is None:
            import asyncpg

            self._pool = await asyncpg.create_pool(dsn=self._dsn, min_size=1, max_size=5)
        return self._pool

    async def query(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [dict(r) for r in rows]

    async def execute(self, sql: str, *params: Any) -> int:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            status = await conn.execute(sql, *params)
        # asyncpg returns e.g. "UPDATE 3" / "INSERT 0 1"
        parts = str(status).split()
        for part in reversed(parts):
            if part.isdigit():
                return int(part)
        return 0

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
