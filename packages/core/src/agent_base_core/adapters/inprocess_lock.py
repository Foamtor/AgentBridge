"""In-process thread lock."""

from __future__ import annotations

import asyncio


class InProcessThreadLock:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._owners: dict[str, str] = {}

    async def try_acquire(self, thread_id: str, run_id: str) -> bool:
        async with self._lock:
            if thread_id in self._owners:
                return False
            self._owners[thread_id] = run_id
            return True

    async def release(self, thread_id: str, run_id: str) -> None:
        async with self._lock:
            owner = self._owners.get(thread_id)
            if owner == run_id:
                del self._owners[thread_id]
