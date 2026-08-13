"""PostgreSQL-backed admin prompt registry."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any


class PostgresPromptRegistry:
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
            Path(__file__).resolve().parents[1] / "migrations" / "017_prompt_registry.sql"
        )
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(migration.read_text(encoding="utf-8"))

    async def list_names(self) -> list[str]:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                "SELECT name FROM bridge_prompts ORDER BY name"
            )
        return [str(row["name"]) for row in rows]

    async def get(self, name: str) -> dict[str, Any] | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                SELECT name, draft_content, draft_version,
                       published_content, published_version
                FROM bridge_prompts WHERE name = $1
                """,
                name,
            )
        return _record_from_row(row) if row is not None else None

    async def put(self, name: str, *, content: str) -> dict[str, Any]:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                INSERT INTO bridge_prompts
                    (name, draft_content, draft_version)
                VALUES ($1, $2, 1)
                ON CONFLICT (name) DO UPDATE SET
                    draft_content = EXCLUDED.draft_content,
                    draft_version = bridge_prompts.draft_version + 1,
                    updated_at = NOW()
                RETURNING name, draft_content, draft_version,
                          published_content, published_version
                """,
                name,
                content,
            )
        return _record_from_row(row)

    async def publish(self, name: str) -> dict[str, Any]:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection, connection.transaction():
            row = await connection.fetchrow(
                """
                    SELECT name, draft_content, draft_version,
                           published_content, published_version
                    FROM bridge_prompts WHERE name = $1 FOR UPDATE
                    """,
                name,
            )
            if row is None:
                raise KeyError(name)
            content = row["draft_content"]
            if content is None:
                content = row["published_content"]
            if content is None:
                raise KeyError(name)
            next_version = max(
                int(row["draft_version"] or 0),
                int(row["published_version"] or 0),
            ) + 1
            row = await connection.fetchrow(
                """
                    UPDATE bridge_prompts
                    SET draft_content = NULL, draft_version = 0,
                        published_content = $2, published_version = $3,
                        updated_at = NOW()
                    WHERE name = $1
                    RETURNING name, draft_content, draft_version,
                              published_content, published_version
                    """,
                name,
                content,
                next_version,
            )
        return _record_from_row(row)

    async def render(self, name: str, /, **vars: str) -> str:
        rec = await self.get(name)
        if rec is None:
            raise FileNotFoundError(f"prompt not found: {name}")
        return str(rec["content"]).format(**vars)

    async def close(self) -> None:
        async with self._pool_lock:
            if self._pool is not None:
                await self._pool.close()
                self._pool = None


def _record_from_row(row: Any) -> dict[str, Any]:
    if row["draft_content"] is not None:
        return {
            "name": row["name"],
            "content": row["draft_content"],
            "status": "draft",
            "version": int(row["draft_version"] or 0),
        }
    if row["published_content"] is not None:
        return {
            "name": row["name"],
            "content": row["published_content"],
            "status": "published",
            "version": int(row["published_version"] or 0),
        }
    return {
        "name": row["name"],
        "content": "",
        "status": "draft",
        "version": 0,
    }
