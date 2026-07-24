"""Memory checkpointer factory (LangGraph MemorySaver)."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver


class MemoryCheckpointerFactory:
    def __init__(self) -> None:
        self._saver: MemorySaver | None = None

    async def setup(self) -> None:
        self._saver = MemorySaver()

    def is_setup(self) -> bool:
        return self._saver is not None

    async def get(self) -> Any:
        if self._saver is None:
            await self.setup()
        return self._saver

    async def teardown(self) -> None:
        self._saver = None
