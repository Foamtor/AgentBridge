"""EventLog protocol — committed outbound envelopes only."""

from __future__ import annotations

from typing import Any, Protocol


class EventLog(Protocol):
    async def append(self, run_id: str, event: dict[str, Any]) -> None: ...

    async def list(self, run_id: str) -> list[dict[str, Any]]: ...
