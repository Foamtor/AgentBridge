"""PostgreSQL persistence for safe, hot-reloadable runtime settings."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


class PostgresConfigProvider:
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
            / "012_runtime_config.sql"
        )
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(migration.read_text(encoding="utf-8"))

    async def get(self, key: str) -> Any | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            value = await connection.fetchval(
                "SELECT value FROM bridge_runtime_config WHERE key = $1", key
            )
        # asyncpg returns decoded JSON with some codecs and a JSON string with
        # others. Normalize at this boundary so callers always see the value.
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    async def set(
        self, key: str, value: Any, *, updated_by: str | None = None
    ) -> None:
        encoded = json.dumps(value, ensure_ascii=False)
        pool = await self._ensure_pool()
        async with pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """
                    INSERT INTO bridge_runtime_config (key, value, updated_by)
                    VALUES ($1, $2::jsonb, $3)
                    ON CONFLICT (key) DO UPDATE SET
                        value = EXCLUDED.value,
                        updated_by = EXCLUDED.updated_by,
                        updated_at = NOW()
                    """,
                key,
                encoded,
                updated_by,
            )
            await connection.execute(
                """
                    INSERT INTO bridge_runtime_config_audit (key, value, updated_by)
                    VALUES ($1, $2::jsonb, $3)
                    """,
                key,
                encoded,
                updated_by,
            )

    async def close(self) -> None:
        async with self._pool_lock:
            if self._pool is not None:
                await self._pool.close()
                self._pool = None
