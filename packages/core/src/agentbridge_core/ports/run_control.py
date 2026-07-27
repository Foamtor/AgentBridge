"""Protocol: RunCancelRegistry."""

from __future__ import annotations

from typing import Any, Protocol


class RunCancelRegistry(Protocol):
    async def register(self, thread_id: str, run_id: str, token: Any) -> None: ...

    async def request_cancel(self, thread_id: str, run_id: str | None = None) -> bool: ...

    async def unregister(self, thread_id: str, run_id: str) -> None: ...
