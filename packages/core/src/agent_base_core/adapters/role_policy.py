"""Role/permission based PolicyEngine."""

from __future__ import annotations

from typing import Any

from agent_base_core.protocol.context import RunContext
from agent_base_core.protocol.tool_meta import get_tool_meta


def _allowed(
    ctx: RunContext, required_roles: list[str], required_permissions: list[str]
) -> bool:
    if "*" in ctx.permissions:
        return True
    if not required_roles and not required_permissions:
        return True
    if required_roles and set(ctx.roles) & set(required_roles):
        return True
    if required_permissions and set(ctx.permissions) & set(required_permissions):
        return True
    return False


class RolePolicyEngine:
    def filter_tools(self, route: str, tools: list[Any], ctx: RunContext) -> list[Any]:
        out: list[Any] = []
        for tool in tools:
            meta = get_tool_meta(tool)
            if _allowed(ctx, meta["required_roles"], meta["required_permissions"]):
                out.append(tool)
        return out

    def decide(self, *, ctx: RunContext, action: str, resource: dict[str, Any]) -> str:
        if action == "list_tools":
            return "allow"
        if action != "invoke_tool":
            return "deny"
        roles = list(resource.get("required_roles") or [])
        perms = list(resource.get("required_permissions") or [])
        return "allow" if _allowed(ctx, roles, perms) else "deny"
