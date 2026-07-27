"""In-memory fake chat model for Gateway tests (no vendor SDK)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any


class FakeChatModel:
    """Returns canned string responses via ainvoke / astream."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or ["ok"])
        self.calls: list[list[Any]] = []

    async def ainvoke(self, messages: list[Any]) -> str:
        self.calls.append(list(messages))
        if not self._responses:
            return ""
        return self._responses.pop(0)

    async def astream(self, messages: list[Any]) -> AsyncIterator[str]:
        text = await self.ainvoke(messages)
        for ch in text:
            yield ch
