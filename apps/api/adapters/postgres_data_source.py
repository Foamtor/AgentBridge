"""Postgres DataSource via asyncpg (api host adapter)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from agentbridge_core.ports.data_source import DataSource

T = TypeVar("T")


class PostgresDataSource:
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

    async def query(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [dict(r) for r in rows]

    async def execute(self, sql: str, *params: Any) -> int:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            status = await conn.execute(sql, *params)
        return _rows_affected(status)

    async def transaction(self, operation: Callable[[DataSource], Awaitable[T]]) -> T:
        """Run an operation on one acquired connection and database transaction."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                return await operation(_PostgresTransaction(conn))

    async def close(self) -> None:
        async with self._pool_lock:
            if self._pool is not None:
                await self._pool.close()
                self._pool = None


class _PostgresTransaction:
    """DataSource view bound to an already-acquired asyncpg connection."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    async def query(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        rows = await self._connection.fetch(sql, *params)
        return [dict(row) for row in rows]

    async def execute(self, sql: str, *params: Any) -> int:
        status = await self._connection.execute(sql, *params)
        return _rows_affected(status)

    async def close(self) -> None:
        """The outer source owns the pool and connection lifecycle."""
        return None


def _rows_affected(status: Any) -> int:
    # asyncpg returns e.g. "UPDATE 3" / "INSERT 0 1".
    for part in reversed(str(status).split()):
        if part.isdigit():
            return int(part)
    return 0
