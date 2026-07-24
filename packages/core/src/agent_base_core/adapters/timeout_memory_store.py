"""MemoryStore with wait_for timeout → empty list (never blocks run)."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Awaitable

from agent_base_core.protocol.context import RunContext


class TimeoutMemoryStore:
    """Wraps an async recall fn; on timeout returns ``[]``."""

    def __init__(
        self,
        recall_fn: Callable[[str, RunContext], Awaitable[list[dict[str, Any]]]]
        | None = None,
    ) -> None:
        self._recall_fn = recall_fn

    async def recall(
        self, query: str, *, ctx: RunContext, timeout: float = 2.0
    ) -> list[dict[str, Any]]:
        if self._recall_fn is None:
            return []

        async def _call() -> list[dict[str, Any]]:
            return await self._recall_fn(query, ctx)

        try:
            return await asyncio.wait_for(_call(), timeout=timeout)
        except TimeoutError:
            return []
