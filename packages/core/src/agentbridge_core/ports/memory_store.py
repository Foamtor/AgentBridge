"""MemoryStore protocol — long-term recall with soft timeout."""

from __future__ import annotations

from typing import Any, Protocol

from agentbridge_core.protocol.context import RunContext


class MemoryStore(Protocol):
    async def recall(
        self, query: str, *, ctx: RunContext, timeout: float = 2.0
    ) -> list[dict[str, Any]]: ...
