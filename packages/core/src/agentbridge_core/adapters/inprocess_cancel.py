"""In-process cancel registry."""

from __future__ import annotations

import asyncio


class InProcessCancelRegistry:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # thread_id -> (run_id, token)
        self._active: dict[str, tuple[str, asyncio.Event]] = {}

    async def register(self, thread_id: str, run_id: str, token: asyncio.Event) -> None:
        if not isinstance(token, asyncio.Event):
            raise TypeError("cancel token must be asyncio.Event")
        async with self._lock:
            token.clear()
            self._active[thread_id] = (run_id, token)

    async def request_cancel(self, thread_id: str, run_id: str | None = None) -> bool:
        async with self._lock:
            entry = self._active.get(thread_id)
            if entry is None:
                return False
            current_run_id, token = entry
            if run_id is not None and run_id != current_run_id:
                return False
            token.set()
            return True

    async def unregister(self, thread_id: str, run_id: str) -> None:
        async with self._lock:
            entry = self._active.get(thread_id)
            if entry is not None and entry[0] == run_id:
                del self._active[thread_id]
