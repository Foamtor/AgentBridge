"""PostgreSQL-backed durable ApprovalStore adapter."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any


class PostgresApprovalStore:
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

    async def create(self, record: dict[str, Any]) -> str:
        approval_id = str(record.get("approval_id") or f"ap-{uuid.uuid4().hex[:12]}")
        sql = """
            INSERT INTO approval_records (
                approval_id, tenant_id, route, run_id, thread_id, storage_key,
                sequence, status, action, requester_context
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10::jsonb)
        """
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                sql,
                approval_id,
                record["tenant_id"],
                record.get("route"),
                record.get("run_id"),
                record.get("thread_id"),
                record.get("storage_key"),
                record.get("sequence"),
                record.get("status", "pending"),
                _json_value(record.get("action")),
                _json_value(record.get("requester_context")),
            )
        return approval_id

    async def get(
        self, approval_id: str, *, tenant_id: str
    ) -> dict[str, Any] | None:
        return await self._fetchrow(
            "SELECT * FROM approval_records WHERE approval_id = $1 AND tenant_id = $2",
            approval_id,
            tenant_id,
        )

    async def resolve(
        self, approval_id: str, *, tenant_id: str, decision: str
    ) -> dict[str, Any] | None:
        return await self._fetchrow(
            """
            UPDATE approval_records
            SET status = 'resolved', decision = $3, updated_at = NOW()
            WHERE approval_id = $1 AND tenant_id = $2 AND status = 'pending'
            RETURNING *
            """,
            approval_id,
            tenant_id,
            decision,
        )

    async def decide(
        self,
        approval_id: str,
        *,
        tenant_id: str,
        decision: str,
        reason: str | None = None,
    ) -> dict[str, Any] | None:
        if decision == "approve":
            status, stored_reason = "approved_pending_execution", None
        elif decision in {"deny", "timeout"}:
            status, stored_reason = "denied", reason or decision
        else:
            raise ValueError(f"unsupported approval decision: {decision}")
        return await self._fetchrow(
            """
            UPDATE approval_records
            SET status = $3, decision = $4, reason = $5, updated_at = NOW()
            WHERE approval_id = $1 AND tenant_id = $2 AND status = 'pending'
            RETURNING *
            """,
            approval_id,
            tenant_id,
            status,
            decision,
            stored_reason,
        )

    async def claim_execution(
        self,
        approval_id: str,
        *,
        tenant_id: str,
        now: datetime,
        lease_seconds: float,
    ) -> dict[str, Any] | None:
        return await self._fetchrow(
            """
            UPDATE approval_records
            SET status = 'executing', execution_started_at = $3,
                execution_lease_expires_at = $4, updated_at = NOW()
            WHERE approval_id = $1 AND tenant_id = $2
              AND status IN ('approved_pending_execution', 'retryable_failed')
            RETURNING *
            """,
            approval_id,
            tenant_id,
            now,
            now + timedelta(seconds=lease_seconds),
        )

    async def mark_succeeded(
        self, approval_id: str, *, tenant_id: str, result: dict[str, Any]
    ) -> dict[str, Any] | None:
        return await self._finish_execution(
            approval_id, tenant_id=tenant_id, status="succeeded", result=result
        )

    async def mark_retryable_failed(
        self, approval_id: str, *, tenant_id: str, error: str
    ) -> dict[str, Any] | None:
        return await self._finish_execution(
            approval_id, tenant_id=tenant_id, status="retryable_failed", error=error
        )

    async def mark_execution_denied(
        self, approval_id: str, *, tenant_id: str, reason: str
    ) -> dict[str, Any] | None:
        return await self._fetchrow(
            """
            UPDATE approval_records
            SET status = 'denied', reason = $3, updated_at = NOW()
            WHERE approval_id = $1 AND tenant_id = $2
              AND status = 'approved_pending_execution'
            RETURNING *
            """,
            approval_id,
            tenant_id,
            reason,
        )

    async def mark_result_delivery_failed(
        self, approval_id: str, *, tenant_id: str, error: str
    ) -> dict[str, Any] | None:
        return await self._fetchrow(
            """
            UPDATE approval_records
            SET result_delivery_error = $3, updated_at = NOW()
            WHERE approval_id = $1 AND tenant_id = $2 AND status = 'succeeded'
            RETURNING *
            """,
            approval_id,
            tenant_id,
            error,
        )

    async def recover_expired_execution(
        self, approval_id: str, *, tenant_id: str, now: datetime
    ) -> dict[str, Any] | None:
        return await self._fetchrow(
            """
            UPDATE approval_records
            SET status = 'retryable_failed', error = 'execution_lease_expired',
                updated_at = NOW()
            WHERE approval_id = $1 AND tenant_id = $2 AND status = 'executing'
              AND execution_lease_expires_at <= $3
            RETURNING *
            """,
            approval_id,
            tenant_id,
            now,
        )

    async def _finish_execution(
        self,
        approval_id: str,
        *,
        tenant_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        return await self._fetchrow(
            """
            UPDATE approval_records
            SET status = $3, result = $4::jsonb, error = $5, updated_at = NOW()
            WHERE approval_id = $1 AND tenant_id = $2 AND status = 'executing'
            RETURNING *
            """,
            approval_id,
            tenant_id,
            status,
            _json_value(result),
            error,
        )

    async def _fetchrow(self, sql: str, *params: Any) -> dict[str, Any] | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(sql, *params)
        return _record_from_row(row) if row is not None else None

    async def close(self) -> None:
        async with self._pool_lock:
            if self._pool is not None:
                await self._pool.close()
                self._pool = None


def _json_value(value: Any) -> str | None:
    return json.dumps(value) if value is not None else None


def _record_from_row(row: Any) -> dict[str, Any]:
    record = dict(row)
    for key in ("action", "requester_context", "result"):
        value = record.get(key)
        if isinstance(value, str):
            record[key] = json.loads(value)
    return record
