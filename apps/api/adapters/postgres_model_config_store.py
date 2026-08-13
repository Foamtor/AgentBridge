"""PostgreSQL persistence for operator-managed LLM connection metadata."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any


class PostgresModelConfigStore:
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
        """Apply the isolated, idempotent migration for existing Compose volumes."""
        migration_dir = Path(__file__).resolve().parents[1] / "migrations"
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            for name in (
                "011_model_configs.sql",
                "013_model_connection_tests.sql",
                "018_model_alias_format.sql",
                "019_model_tool_call_capability.sql",
            ):
                await connection.execute((migration_dir / name).read_text(encoding="utf-8"))

    async def list(self) -> list[dict[str, Any]]:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                "SELECT * FROM bridge_model_configs ORDER BY alias"
            )
        return [dict(row) for row in rows]

    async def get(self, alias: str) -> dict[str, Any] | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT * FROM bridge_model_configs WHERE alias = $1", alias
            )
        return dict(row) if row is not None else None

    async def create(self, record: dict[str, Any]) -> dict[str, Any] | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                INSERT INTO bridge_model_configs
                    (alias, provider, api_base, model_name, api_key_ciphertext,
                     temperature, enabled, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (alias) DO NOTHING
                RETURNING *
                """,
                record["alias"], record["provider"], record["api_base"],
                record["model_name"], record["api_key_ciphertext"],
                record["temperature"], record["enabled"], record["created_by"],
            )
        return dict(row) if row is not None else None

    async def update(self, alias: str, record: dict[str, Any]) -> dict[str, Any] | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                UPDATE bridge_model_configs
                SET api_base = $2, model_name = $3, api_key_ciphertext = $4,
                    temperature = $5, enabled = $6, last_test_status = $7,
                    last_tested_at = $8, last_test_latency_ms = $9,
                    last_test_error = $10, last_test_capability = $11,
                    updated_at = NOW()
                WHERE alias = $1
                RETURNING *
                """,
                alias, record["api_base"], record["model_name"],
                record["api_key_ciphertext"], record["temperature"], record["enabled"],
                record.get("last_test_status"), record.get("last_tested_at"),
                record.get("last_test_latency_ms"), record.get("last_test_error"),
                record.get("last_test_capability"),
            )
        return dict(row) if row is not None else None

    async def record_test(
        self,
        alias: str,
        *,
        status: str,
        latency_ms: int | None,
        error: str | None,
        capability: str | None,
    ) -> dict[str, Any] | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                UPDATE bridge_model_configs
                SET last_test_status = $2, last_tested_at = NOW(),
                    last_test_latency_ms = $3, last_test_error = $4,
                    last_test_capability = $5, updated_at = NOW()
                WHERE alias = $1
                RETURNING *
                """,
                alias, status, latency_ms, error, capability,
            )
        return dict(row) if row is not None else None

    async def delete(self, alias: str) -> bool:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            result = await connection.execute(
                "DELETE FROM bridge_model_configs WHERE alias = $1", alias
            )
        return result == "DELETE 1"

    async def close(self) -> None:
        async with self._pool_lock:
            if self._pool is not None:
                await self._pool.close()
                self._pool = None
