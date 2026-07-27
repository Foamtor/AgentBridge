"""Protocol: ThreadLock."""

from __future__ import annotations

from typing import Protocol


class ThreadLock(Protocol):
    async def try_acquire(self, thread_id: str, run_id: str) -> bool: ...

    async def release(self, thread_id: str, run_id: str) -> None: ...
