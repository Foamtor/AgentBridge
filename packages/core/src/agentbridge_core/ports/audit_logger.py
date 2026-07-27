"""AuditLogger protocol."""

from __future__ import annotations

from typing import Any, Protocol


class AuditLogger(Protocol):
    async def log(
        self,
        *,
        user_id: str,
        tenant_id: str,
        action: str,
        resource: str,
        detail: dict[str, Any],
        result: str,
    ) -> None: ...
