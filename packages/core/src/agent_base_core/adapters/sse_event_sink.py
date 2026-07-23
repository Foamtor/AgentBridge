"""SSE event sink backed by asyncio.Queue."""

from __future__ import annotations

import asyncio
from typing import Any


class SseEventSink:
    def __init__(self, queue: asyncio.Queue[dict[str, Any] | None]) -> None:
        self._queue = queue

    async def emit(self, event: dict[str, Any]) -> None:
        await self._queue.put(event)

    async def close(self) -> None:
        await self._queue.put(None)
