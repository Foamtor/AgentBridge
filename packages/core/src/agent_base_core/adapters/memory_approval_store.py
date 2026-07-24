"""In-memory ApprovalStore with tenant isolation."""

from __future__ import annotations

import uuid
from typing import Any


class MemoryApprovalStore:
    def __init__(self) -> None:
        self._by_id: dict[str, dict[str, Any]] = {}

    async def create(self, record: dict[str, Any]) -> str:
        approval_id = str(record.get("approval_id") or f"ap-{uuid.uuid4().hex[:12]}")
        row = dict(record)
        row["approval_id"] = approval_id
        row.setdefault("status", "pending")
        self._by_id[approval_id] = row
        return approval_id

    async def get(
        self, approval_id: str, *, tenant_id: str
    ) -> dict[str, Any] | None:
        raw = self._by_id.get(approval_id)
        if raw is None or raw.get("tenant_id") != tenant_id:
            return None
        return dict(raw)

    async def resolve(
        self,
        approval_id: str,
        *,
        tenant_id: str,
        decision: str,
    ) -> dict[str, Any] | None:
        raw = self._by_id.get(approval_id)
        if raw is None or raw.get("tenant_id") != tenant_id:
            return None
        if raw.get("status") != "pending":
            return None
        raw = dict(raw)
        raw["status"] = "resolved"
        raw["decision"] = decision
        self._by_id[approval_id] = raw
        return dict(raw)
