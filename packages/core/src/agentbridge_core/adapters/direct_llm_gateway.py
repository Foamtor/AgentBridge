"""Direct LLMGateway — delegates to an injected chat model (ainvoke/astream)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from agentbridge_core.protocol.context import RunContext


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
        tools: list[Any] | None = None,
        tool_choice: str | None = None,
    ) -> Any:
        _ = (ctx, model)
        backend = self._model
        if tools:
            bind_tools = getattr(backend, "bind_tools", None)
            if not callable(bind_tools):
                raise RuntimeError("llm_tool_binding_unsupported")
            kwargs = {"tool_choice": tool_choice} if tool_choice else {}
            backend = bind_tools(list(tools), **kwargs)
        ainvoke = getattr(backend, "ainvoke", None)
        if callable(ainvoke):
            return await ainvoke(messages)
        invoke = getattr(backend, "invoke", None)
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
