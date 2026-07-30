"""ApprovalStore protocol — pending human-in-the-loop decisions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol


class ApprovalStore(Protocol):
    async def create(self, record: dict[str, Any]) -> str:
        """Persist pending approval; returns approval_id."""

    async def get(
        self, approval_id: str, *, tenant_id: str
    ) -> dict[str, Any] | None: ...

    async def resolve(
        self,
        approval_id: str,
        *,
        tenant_id: str,
        decision: str,
    ) -> dict[str, Any] | None:
        """Mark resolved; returns updated record or None if missing/cross-tenant."""

    async def decide(
        self,
        approval_id: str,
        *,
        tenant_id: str,
        decision: str,
        reason: str | None = None,
    ) -> dict[str, Any] | None: ...

    async def claim_execution(
        self,
        approval_id: str,
        *,
        tenant_id: str,
        now: datetime,
        lease_seconds: float,
    ) -> dict[str, Any] | None: ...

    async def mark_succeeded(
        self,
        approval_id: str,
        *,
        tenant_id: str,
        result: dict[str, Any],
    ) -> dict[str, Any] | None: ...

    async def mark_retryable_failed(
        self,
        approval_id: str,
        *,
        tenant_id: str,
        error: str,
    ) -> dict[str, Any] | None: ...

    async def mark_execution_denied(
        self,
        approval_id: str,
        *,
        tenant_id: str,
        reason: str,
    ) -> dict[str, Any] | None: ...

    async def mark_result_delivery_failed(
        self,
        approval_id: str,
        *,
        tenant_id: str,
        error: str,
    ) -> dict[str, Any] | None: ...

    async def recover_expired_execution(
        self,
        approval_id: str,
        *,
        tenant_id: str,
        now: datetime,
    ) -> dict[str, Any] | None: ...
