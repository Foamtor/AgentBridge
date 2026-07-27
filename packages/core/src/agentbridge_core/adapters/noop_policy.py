"""No-op PolicyEngine (allow all)."""

from __future__ import annotations

from typing import Any

from agentbridge_core.protocol.context import RunContext


class NoopPolicyEngine:
    def filter_tools(self, route: str, tools: list[Any], ctx: RunContext) -> list[Any]:
        return list(tools)

    def decide(self, *, ctx: RunContext, action: str, resource: dict[str, Any]) -> str:
        return "allow"
