"""ApprovalStore protocol — pending human-in-the-loop decisions."""

from __future__ import annotations

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
