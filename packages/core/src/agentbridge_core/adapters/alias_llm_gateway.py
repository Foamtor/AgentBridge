"""Alias-routing LLMGateway for LLM_BACKEND=gateway."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from agentbridge_core.adapters.direct_llm_gateway import DirectLLMGateway
from agentbridge_core.protocol.context import RunContext


class AliasLLMGateway:
    """Resolve ``model`` alias to an injected backend; domains never see vendors."""

    def __init__(
        self,
        models: dict[str, Any],
        *,
        default_alias: str = "default",
    ) -> None:
        if not models:
            raise ValueError("models must be non-empty")
        if default_alias not in models:
            raise ValueError(f"default_alias {default_alias!r} missing from models")
        self._models = dict(models)
        self._default = default_alias

    def _delegate(self, model: str | None) -> DirectLLMGateway:
        alias = model or self._default
        if alias not in self._models:
            raise KeyError(f"unknown model alias: {alias}")
        return DirectLLMGateway(self._models[alias])

    def replace_models(self, models: dict[str, Any]) -> None:
        """Atomically replace host-wired aliases without exposing vendors to domains."""
        if not models:
            raise ValueError("models must be non-empty")
        if self._default not in models:
            raise ValueError(f"default alias {self._default!r} missing")
        self._models = dict(models)

    def aliases(self) -> tuple[str, ...]:
        return tuple(sorted(self._models))

    async def chat(
        self,
        messages: list[Any],
        *,
        ctx: RunContext,
        model: str | None = None,
        tools: list[Any] | None = None,
        tool_choice: str | None = None,
    ) -> Any:
        return await self._delegate(model).chat(
            messages,
            ctx=ctx,
            model=model,
            tools=tools,
            tool_choice=tool_choice,
        )

    async def stream(
        self,
        messages: list[Any],
        *,
        ctx: RunContext,
        model: str | None = None,
    ) -> AsyncIterator[Any]:
        async for chunk in self._delegate(model).stream(
            messages, ctx=ctx, model=model
        ):
            yield chunk
