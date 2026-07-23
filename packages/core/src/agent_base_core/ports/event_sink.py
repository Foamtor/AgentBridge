"""Protocol: EventSink."""

from __future__ import annotations

from typing import Any, Protocol


class EventSink(Protocol):
    async def emit(self, event: dict[str, Any]) -> None: ...

    async def close(self) -> None: ...
