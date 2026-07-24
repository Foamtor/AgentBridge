"""Direct LLMGateway — delegates to an injected chat model (ainvoke/astream)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from agent_base_core.protocol.context import RunContext


class DirectLLMGateway:
    """Passthrough adapter: domain/runtime still supply the concrete model."""

    def __init__(self, model: Any) -> None:
        self._model = model

    async def chat(
        self,
        messages: list[Any],
        *,
        ctx: RunContext,
        model: str | None = None,
    ) -> Any:
        _ = (ctx, model)
        ainvoke = getattr(self._model, "ainvoke", None)
        if callable(ainvoke):
            return await ainvoke(messages)
        invoke = getattr(self._model, "invoke", None)
        if callable(invoke):
            return invoke(messages)
        raise TypeError("injected model has no ainvoke/invoke")

    async def stream(
        self,
        messages: list[Any],
        *,
        ctx: RunContext,
        model: str | None = None,
    ) -> AsyncIterator[Any]:
        _ = (ctx, model)
        astream = getattr(self._model, "astream", None)
        if callable(astream):
            async for chunk in astream(messages):
                yield chunk
            return
        # Fallback: single chat response as one chunk.
        yield await self.chat(messages, ctx=ctx, model=model)
