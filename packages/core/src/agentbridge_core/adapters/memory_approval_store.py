"""In-memory ApprovalStore with tenant isolation."""

from __future__ import annotations

import asyncio
import copy
import uuid
from datetime import datetime, timedelta
from typing import Any


class MemoryApprovalStore:
    def __init__(self) -> None:
        self._by_id: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def create(self, record: dict[str, Any]) -> str:
        approval_id = str(record.get("approval_id") or f"ap-{uuid.uuid4().hex[:12]}")
        row = copy.deepcopy(record)
        row["approval_id"] = approval_id
        row.setdefault("status", "pending")
        async with self._lock:
            self._by_id[approval_id] = row
        return approval_id

    async def get(
        self, approval_id: str, *, tenant_id: str
    ) -> dict[str, Any] | None:
        async with self._lock:
            raw = self._by_id.get(approval_id)
            if raw is None or raw.get("tenant_id") != tenant_id:
                return None
            return copy.deepcopy(raw)

    async def resolve(
        self,
        approval_id: str,
        *,
        tenant_id: str,
        decision: str,
    ) -> dict[str, Any] | None:
        """Atomically claim a pending approval. Returns None if missing/already resolved."""
        async with self._lock:
            raw = self._by_id.get(approval_id)
            if raw is None or raw.get("tenant_id") != tenant_id:
                return None
            if raw.get("status") != "pending":
                return None
            raw = dict(raw)
            raw["status"] = "resolved"
            raw["decision"] = decision
            self._by_id[approval_id] = raw
            return copy.deepcopy(raw)

    async def decide(
        self,
        approval_id: str,
        *,
        tenant_id: str,
        decision: str,
        reason: str | None = None,
    ) -> dict[str, Any] | None:
        async with self._lock:
            raw = self._pending_for(approval_id, tenant_id)
            if raw is None:
                return None
            if decision == "approve":
                raw["status"] = "approved_pending_execution"
                raw["decision"] = "approve"
            elif decision in {"deny", "timeout"}:
                raw["status"] = "denied"
                raw["decision"] = decision
                raw["reason"] = reason or decision
            else:
                raise ValueError(f"unsupported approval decision: {decision}")
            self._by_id[approval_id] = raw
            return copy.deepcopy(raw)

    async def claim_execution(
        self,
        approval_id: str,
        *,
        tenant_id: str,
        now: datetime,
        lease_seconds: float,
    ) -> dict[str, Any] | None:
        async with self._lock:
            raw = self._record_for(approval_id, tenant_id)
            if raw is None or raw.get("status") not in {
                "approved_pending_execution",
                "retryable_failed",
            }:
                return None
            raw["status"] = "executing"
            raw["execution_started_at"] = now
            raw["execution_lease_expires_at"] = now + timedelta(seconds=lease_seconds)
            self._by_id[approval_id] = raw
            return copy.deepcopy(raw)

    async def mark_succeeded(
        self, approval_id: str, *, tenant_id: str, result: dict[str, Any]
    ) -> dict[str, Any] | None:
        return await self._finish_execution(
            approval_id, tenant_id=tenant_id, status="succeeded", result=copy.deepcopy(result)
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
        async with self._lock:
            raw = self._record_for(approval_id, tenant_id)
            if raw is None or raw.get("status") != "approved_pending_execution":
                return None
            raw["status"] = "denied"
            raw["reason"] = reason
            self._by_id[approval_id] = raw
            return copy.deepcopy(raw)

    async def mark_result_delivery_failed(
        self, approval_id: str, *, tenant_id: str, error: str
    ) -> dict[str, Any] | None:
        async with self._lock:
            raw = self._record_for(approval_id, tenant_id)
            if raw is None or raw.get("status") != "succeeded":
                return None
            raw["result_delivery_error"] = error
            self._by_id[approval_id] = raw
            return copy.deepcopy(raw)

    async def recover_expired_execution(
        self, approval_id: str, *, tenant_id: str, now: datetime
    ) -> dict[str, Any] | None:
        async with self._lock:
            raw = self._record_for(approval_id, tenant_id)
            expires_at = raw.get("execution_lease_expires_at") if raw else None
            if (
                raw is None
                or raw.get("status") != "executing"
                or not isinstance(expires_at, datetime)
                or expires_at > now
            ):
                return None
            raw["status"] = "retryable_failed"
            raw["error"] = "execution_lease_expired"
            self._by_id[approval_id] = raw
            return copy.deepcopy(raw)

    def _record_for(self, approval_id: str, tenant_id: str) -> dict[str, Any] | None:
        raw = self._by_id.get(approval_id)
        if raw is None or raw.get("tenant_id") != tenant_id:
            return None
        return dict(raw)

    def _pending_for(self, approval_id: str, tenant_id: str) -> dict[str, Any] | None:
        raw = self._record_for(approval_id, tenant_id)
        if raw is None or raw.get("status") != "pending":
            return None
        return raw

    async def _finish_execution(
        self,
        approval_id: str,
        *,
        tenant_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        async with self._lock:
            raw = self._record_for(approval_id, tenant_id)
            if raw is None or raw.get("status") != "executing":
                return None
            raw["status"] = status
            if result is not None:
                raw["result"] = result
            if error is not None:
                raw["error"] = error
            self._by_id[approval_id] = raw
            return copy.deepcopy(raw)
