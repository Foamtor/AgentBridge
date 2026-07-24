"""PolicyEngine protocol."""

from __future__ import annotations

from typing import Any, Protocol

from agent_base_core.protocol.context import RunContext

PolicyDecision = str  # allow|deny|require_approval|mask


class PolicyEngine(Protocol):
    def filter_tools(self, route: str, tools: list[Any], ctx: RunContext) -> list[Any]: ...

    def decide(
        self, *, ctx: RunContext, action: str, resource: dict[str, Any]
    ) -> PolicyDecision: ...
