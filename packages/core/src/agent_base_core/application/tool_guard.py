"""Wrap tools so invoke_tool policy is checked before execution."""

from __future__ import annotations

import logging
from typing import Any

from agent_base_core.ports.audit_logger import AuditLogger
from agent_base_core.ports.policy import PolicyEngine
from agent_base_core.protocol.context import RunContext
from agent_base_core.registry.tool_meta import get_tool_meta

logger = logging.getLogger(__name__)


def _resource_for(tool: Any) -> dict[str, Any]:
    meta = get_tool_meta(tool)
    name = getattr(tool, "name", None) or getattr(tool, "__name__", "tool")
    return {
        "name": name,
        "required_roles": meta["required_roles"],
        "required_permissions": meta["required_permissions"],
    }


def guard_tools(
    tools: list[Any],
    *,
    policy: PolicyEngine,
    ctx: RunContext,
    audit: AuditLogger | None = None,
) -> list[Any]:
    """Return tools wrapped with invoke_tool policy checks."""
    out: list[Any] = []
    for tool in tools:
        out.append(_GuardProxy(tool, policy=policy, ctx=ctx, audit=audit))
    return out


class _GuardProxy:
    """Lightweight proxy: prefer .ainvoke/.invoke; fall back to .func/.coroutine."""

    def __init__(
        self,
        tool: Any,
        *,
        policy: PolicyEngine,
        ctx: RunContext,
        audit: AuditLogger | None,
    ) -> None:
        self.__dict__["_tool"] = tool
        self.__dict__["_policy"] = policy
        self.__dict__["_ctx"] = ctx
        self.__dict__["_audit"] = audit

    def __getattr__(self, name: str) -> Any:
        return getattr(self._tool, name)

    async def _audit_denied(self, resource: dict[str, Any]) -> None:
        if self._audit is None:
            return
        await self._audit.log(
            user_id=self._ctx.user_id,
            tenant_id=self._ctx.tenant_id,
            action="invoke_tool",
            resource=str(resource.get("name")),
            detail={"decision": "deny"},
            result="denied",
        )

    def _decide(self) -> str:
        return self._policy.decide(
            ctx=self._ctx, action="invoke_tool", resource=_resource_for(self._tool)
        )

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        if self._decide() != "allow":
            # sync path: best-effort audit skip (async logger)
            return "forbidden"
        inv = getattr(self._tool, "invoke", None)
        if callable(inv):
            return inv(*args, **kwargs)
        func = getattr(self._tool, "func", None)
        if callable(func):
            return func(*args, **kwargs)
        raise TypeError("tool has no invoke/func")

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        if self._decide() != "allow":
            await self._audit_denied(_resource_for(self._tool))
            return "forbidden"
        ainv = getattr(self._tool, "ainvoke", None)
        if callable(ainv):
            return await ainv(*args, **kwargs)
        inv = getattr(self._tool, "invoke", None)
        if callable(inv):
            return inv(*args, **kwargs)
        coro = getattr(self._tool, "coroutine", None)
        if callable(coro):
            return await coro(*args, **kwargs)
        func = getattr(self._tool, "func", None)
        if callable(func):
            return func(*args, **kwargs)
        raise TypeError("tool has no ainvoke/invoke/coroutine/func")
