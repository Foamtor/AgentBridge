"""GET/POST /admin/tools — tool directory, matrix, optional invoke."""

from __future__ import annotations

import inspect
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from agent_base_core.application.tool_guard import guard_tools
from agent_base_core.protocol.context import RunContext
from agent_base_core.protocol.tool_meta import get_tool_meta
from auth.rbac import require_permission
from routes.admin_common import admin_ctx

router = APIRouter(prefix="/admin", tags=["admin"])


def _tool_name(tool: Any) -> str:
    return str(getattr(tool, "name", None) or getattr(tool, "__name__", "tool"))


def _tool_description(tool: Any) -> str:
    desc = getattr(tool, "description", None)
    return str(desc) if desc else ""


def _iter_tools(tools_registry: Any) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    for route in tools_registry.keys():
        try:
            raw = tools_registry.get(route)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(raw, list):
            raw = list(raw) if raw else []
        for tool in raw:
            out.append((route, tool))
    return out


def _find_tool(tools_registry: Any, name: str) -> tuple[str, Any] | None:
    for route, tool in _iter_tools(tools_registry):
        if _tool_name(tool) == name:
            return route, tool
    return None


def _matrix_roles(settings: Any) -> list[str]:
    raw = str(getattr(settings, "policy_matrix_roles", "admin,viewer"))
    return [x.strip() for x in raw.split(",") if x.strip()]


def _build_matrix(
  policy: Any,
  *,
  route: str,
  tool: Any,
  roles: list[str],
) -> dict[str, str]:
    row: dict[str, str] = {}
    for role in roles:
        ctx = RunContext(roles=[role], permissions=[])
        filtered = policy.filter_tools(route, [tool], ctx)
        row[role] = "allow" if filtered else "deny"
    return row


@router.get("/tools")
async def list_tools(request: Request) -> dict[str, Any]:
    ctx = admin_ctx(request)
    require_permission(ctx, "admin:tools")
    settings = request.app.state.settings
    policy = request.app.state.policy
    roles = _matrix_roles(settings)
    tools_out: list[dict[str, Any]] = []
    matrix_tools: dict[str, dict[str, str]] = {}
    for route, tool in _iter_tools(request.app.state.tools):
        name = _tool_name(tool)
        meta = get_tool_meta(tool)
        tools_out.append(
            {
                "name": name,
                "domain": route,
                "description": _tool_description(tool),
                "required_permissions": meta["required_permissions"],
                "required_roles": meta["required_roles"],
                "invoke_allowed": bool(settings.admin_tool_invoke_enabled),
            }
        )
        matrix_tools[name] = _build_matrix(
            policy, route=route, tool=tool, roles=roles
        )
    tools_out.sort(key=lambda t: (t["domain"], t["name"]))
    return {
        "tools": tools_out,
        "matrix": {"roles": roles, "tools": matrix_tools},
    }


async def _invoke_tool(tool: Any, arguments: dict[str, Any]) -> Any:
    ainvoke = getattr(tool, "ainvoke", None)
    if callable(ainvoke):
        result = ainvoke(arguments)
        if inspect.isawaitable(result):
            return await result
        return result
    invoke = getattr(tool, "invoke", None)
    if callable(invoke):
        return invoke(arguments)
    func = getattr(tool, "func", None)
    if callable(func):
        result = func(**arguments)
        if inspect.isawaitable(result):
            return await result
        return result
    raise HTTPException(
        status_code=400,
        detail={"code": "tool_not_invokable", "message": "tool has no invoke entrypoint"},
    )


@router.post("/tools/{name}/invoke")
async def invoke_tool(
    name: str, request: Request, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    ctx = admin_ctx(request)
    require_permission(ctx, "admin:tools")
    settings = request.app.state.settings
    if not settings.admin_tool_invoke_enabled:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "tool_invoke_disabled",
                "message": "admin tool invoke is disabled",
            },
        )
    found = _find_tool(request.app.state.tools, name)
    if found is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "tool_not_found", "message": f"tool {name} not found"},
        )
    route, tool = found
    policy = request.app.state.policy
    audit = getattr(request.app.state, "audit", None)
    guarded = guard_tools([tool], policy=policy, ctx=ctx, audit=audit)
    if not guarded:
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": "tool invoke denied by policy"},
        )
    arguments = dict((body or {}).get("arguments") or {})
    try:
        result = await _invoke_tool(guarded[0], arguments)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400,
            detail={"code": "tool_invoke_failed", "message": str(exc)},
        ) from exc
    if audit is not None:
        await audit.log(
            user_id=ctx.user_id or "",
            tenant_id=ctx.tenant_id or "default",
            action="admin.tool_invoke",
            resource=f"tool:{name}",
            result="ok",
            detail={"route": route, "arguments": arguments},
        )
    return {"ok": True, "result": result}
