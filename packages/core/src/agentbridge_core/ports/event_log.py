"""EventLog protocol — committed outbound envelopes only (tenant-scoped)."""

from __future__ import annotations

from typing import Any, Protocol


class EventLog(Protocol):
    async def append(
        self, run_id: str, event: dict[str, Any], *, tenant_id: str
    ) -> None: ...

    async def list(
        self, run_id: str, *, tenant_id: str
    ) -> list[dict[str, Any]]: ...
