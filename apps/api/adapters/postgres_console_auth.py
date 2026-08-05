"""PostgreSQL adapter for host-owned local console authentication."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any


class PostgresConsoleAuthStore:
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

                self._pool = await asyncpg.create_pool(dsn=self._dsn, min_size=1, max_size=5)
        return self._pool

    async def get_admin(self, username: str) -> dict[str, Any] | None:
        return await self._fetchrow("SELECT * FROM console_admins WHERE username = $1", username)

    async def create_admin(
        self, username: str, password_hash: str, *, must_change_password: bool
    ) -> bool:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                INSERT INTO console_admins (username, password_hash, must_change_password)
                VALUES ($1, $2, $3)
                ON CONFLICT (username) DO NOTHING
                RETURNING username
                """,
                username,
                password_hash,
                must_change_password,
            )
        return row is not None

    async def update_admin_password(
        self, username: str, password_hash: str, *, must_change_password: bool,
        initial_password_issued_at: datetime | None = None
    ) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                UPDATE console_admins
                SET password_hash = $2, must_change_password = $3,
                    password_version = password_version + 1,
                    password_changed_at = CASE WHEN $3 THEN password_changed_at ELSE NOW() END,
                    initial_password_issued_at = $4
                WHERE username = $1
                """,
                username,
                password_hash,
                must_change_password,
                initial_password_issued_at,
            )

    async def create_session(
        self,
        session_hash: str,
        username: str,
        kind: str,
        *,
        created_at: datetime,
        expires_at: datetime,
    ) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO console_sessions
                    (session_hash, username, kind, created_at, last_seen_at, expires_at)
                VALUES ($1, $2, $3, $4, $4, $5)
                """,
                session_hash,
                username,
                kind,
                created_at,
                expires_at,
            )

    async def get_session(self, session_hash: str) -> dict[str, Any] | None:
        return await self._fetchrow(
            "SELECT * FROM console_sessions WHERE session_hash = $1", session_hash
        )

    async def touch_session(
        self, session_hash: str, *, last_seen_at: datetime, expires_at: datetime
    ) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                UPDATE console_sessions
                SET last_seen_at = $2, expires_at = $3
                WHERE session_hash = $1 AND revoked_at IS NULL
                """,
                session_hash,
                last_seen_at,
                expires_at,
            )

    async def revoke_session(self, session_hash: str, *, revoked_at: datetime) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "UPDATE console_sessions SET revoked_at = $2 WHERE session_hash = $1",
                session_hash,
                revoked_at,
            )

    async def revoke_all_sessions(self, username: str, *, revoked_at: datetime) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "UPDATE console_sessions SET revoked_at = $2 WHERE username = $1 AND revoked_at IS NULL",
                username,
                revoked_at,
            )

    async def get_login_failures(self, bucket_key: str) -> dict[str, Any] | None:
        return await self._fetchrow(
            "SELECT * FROM console_login_attempts WHERE bucket_key = $1", bucket_key
        )

    async def record_login_failure(self, bucket_key: str, *, now: datetime) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO console_login_attempts (bucket_key, failures, first_failure_at, last_failure_at)
                VALUES ($1, 1, $2, $2)
                ON CONFLICT (bucket_key) DO UPDATE SET
                    failures = console_login_attempts.failures + 1,
                    last_failure_at = EXCLUDED.last_failure_at
                """,
                bucket_key,
                now,
            )

    async def clear_login_failures(self, bucket_key: str) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "DELETE FROM console_login_attempts WHERE bucket_key = $1", bucket_key
            )

    async def _fetchrow(self, sql: str, *params: Any) -> dict[str, Any] | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(sql, *params)
        return dict(row) if row is not None else None

    async def close(self) -> None:
        async with self._pool_lock:
            if self._pool is not None:
                await self._pool.close()
                self._pool = None
