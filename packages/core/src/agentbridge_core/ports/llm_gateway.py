"""LLMGateway protocol — model IO via host-injected backend."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from agentbridge_core.protocol.context import RunContext


class LLMGateway(Protocol):
    async def chat(
        self,
        messages: list[Any],
        *,
        ctx: RunContext,
        model: str | None = None,
        tools: list[Any] | None = None,
        tool_choice: str | None = None,
    ) -> Any: ...

    def stream(
        self,
        messages: list[Any],
        *,
        ctx: RunContext,
        model: str | None = None,
    ) -> AsyncIterator[Any]: ...
