"""In-memory AuditLogger for tests."""

from __future__ import annotations

from typing import Any


class MemoryAuditLogger:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def log(
        self,
        *,
        user_id: str,
        tenant_id: str,
        action: str,
        resource: str,
        detail: dict[str, Any],
        result: str,
    ) -> None:
        self.records.append(
            {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "action": action,
                "resource": resource,
                "detail": detail,
                "result": result,
            }
        )
