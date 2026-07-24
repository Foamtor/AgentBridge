"""Wrap tools so invoke_tool policy is checked before execution."""

from __future__ import annotations

import asyncio
import copy
import logging
from collections.abc import Coroutine
from typing import Any

from agent_base_core.ports.audit_logger import AuditLogger
from agent_base_core.ports.policy import PolicyEngine
from agent_base_core.protocol.context import RunContext
from agent_base_core.protocol.tool_meta import get_tool_meta

logger = logging.getLogger(__name__)

# Placeholder default when RunContext.policy_bundle_version is empty.
_POLICY_VERSION = "role_policy/v1"

try:
    from langchain_core.tools import BaseTool
except ImportError:  # pragma: no cover
    BaseTool = ()  # type: ignore[misc, assignment]


def _resource_for(tool: Any) -> dict[str, Any]:
    meta = get_tool_meta(tool)
    name = getattr(tool, "name", None) or getattr(tool, "__name__", "tool")
    return {
        "name": name,
        "required_roles": meta["required_roles"],
        "required_permissions": meta["required_permissions"],
    }


def _deny_reason_code(resource: dict[str, Any]) -> str:
    roles = list(resource.get("required_roles") or [])
    perms = list(resource.get("required_permissions") or [])
    if roles and not perms:
        return "role_mismatch"
    if perms and not roles:
        return "permission_mismatch"
    return "policy_deny"


def _policy_version(ctx: RunContext) -> str:
    return (ctx.policy_bundle_version or "").strip() or _POLICY_VERSION


def _deny_audit_detail(resource: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    return {
        "decision": "deny",
        "reason_code": _deny_reason_code(resource),
        "policy_version": _policy_version(ctx),
    }


def _schedule_audit(coro: Coroutine[Any, Any, None]) -> None:
    """Best-effort audit from sync paths (ToolNode may call sync func)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        try:
            asyncio.run(coro)
        except Exception:  # noqa: BLE001
            logger.exception("sync invoke deny audit failed")
        return
    loop.create_task(coro)


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
        if BaseTool and isinstance(tool, BaseTool):
            out.append(_wrap_base_tool(tool, policy=policy, ctx=ctx, audit=audit))
        else:
            out.append(_GuardProxy(tool, policy=policy, ctx=ctx, audit=audit))
    return out


def _wrap_base_tool(
    tool: Any,
    *,
    policy: PolicyEngine,
    ctx: RunContext,
    audit: AuditLogger | None,
) -> Any:
    """Copy BaseTool and wrap ainvoke/invoke — keep coroutine signature intact.

    Replacing ``coroutine`` with a bare ``*args, **kwargs`` wrapper breaks
    LangChain ``InjectedToolArg`` (e.g. RunnableConfig), because injection
    inspects the coroutine signature. Wrapping ainvoke/invoke lets
    StructuredTool inject config first, then our policy check runs.
    """
    guarded = copy.copy(tool)
    resource = _resource_for(tool)
    orig_ainvoke = tool.ainvoke
    orig_invoke = tool.invoke

    def _decide() -> str:
        return policy.decide(ctx=ctx, action="invoke_tool", resource=resource)

    async def _audit_denied() -> None:
        if audit is None:
            return
        await audit.log(
            user_id=ctx.user_id,
            tenant_id=ctx.tenant_id,
            action="invoke_tool",
            resource=str(resource.get("name")),
            detail=_deny_audit_detail(resource, ctx),
            result="denied",
        )

    async def guarded_ainvoke(
        input: Any, config: Any | None = None, **kwargs: Any
    ) -> Any:
        if _decide() != "allow":
            await _audit_denied()
            return "forbidden"
        return await orig_ainvoke(input, config=config, **kwargs)

    def guarded_invoke(input: Any, config: Any | None = None, **kwargs: Any) -> Any:
        if _decide() != "allow":
            _schedule_audit(_audit_denied())
            return "forbidden"
        return orig_invoke(input, config=config, **kwargs)

    object.__setattr__(guarded, "ainvoke", guarded_ainvoke)
    object.__setattr__(guarded, "invoke", guarded_invoke)
    return guarded


class _GuardProxy:
    """Lightweight proxy for non-BaseTool test doubles."""

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
            detail=_deny_audit_detail(resource, self._ctx),
            result="denied",
        )

    def _decide(self) -> str:
        return self._policy.decide(
            ctx=self._ctx, action="invoke_tool", resource=_resource_for(self._tool)
        )

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        if self._decide() != "allow":
            _schedule_audit(self._audit_denied(_resource_for(self._tool)))
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
