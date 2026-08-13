"""Prompt management APIs."""

from __future__ import annotations

import inspect
from typing import Any

from auth.rbac import require_permission
from fastapi import APIRouter, HTTPException, Request

from routes.admin_common import admin_ctx

router = APIRouter(prefix="/prompts", tags=["prompts"])


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def _require_prompt_read(ctx) -> None:
    if "*" in ctx.permissions or "admin:prompts" in ctx.permissions:
        return
    if "admin:read" in ctx.permissions:
        return
    raise HTTPException(
        status_code=403,
        detail={"code": "forbidden", "message": "missing admin:prompts or admin:read"},
    )


@router.get("")
async def list_prompts(request: Request) -> dict[str, Any]:
    ctx = admin_ctx(request)
    _require_prompt_read(ctx)
    registry = request.app.state.prompt_registry
    names = await _maybe_await(registry.list_names())
    return {"items": [{"name": n} for n in names]}


@router.get("/{name}")
async def get_prompt(name: str, request: Request) -> dict[str, Any]:
    ctx = admin_ctx(request)
    _require_prompt_read(ctx)
    registry = request.app.state.prompt_registry
    rec = await _maybe_await(registry.get(name))
    if rec is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "prompt_not_found", "message": f"prompt {name} not found"},
        )
    return rec


@router.put("/{name}")
async def put_prompt(
    name: str, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    ctx = admin_ctx(request)
    require_permission(ctx, "admin:prompts")
    content = body.get("content")
    if not isinstance(content, str):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_body", "message": "content must be a string"},
        )
    registry = request.app.state.prompt_registry
    rec = await _maybe_await(registry.put(name, content=content))
    audit = getattr(request.app.state, "audit", None)
    if audit is not None:
        await audit.log(
            user_id=ctx.user_id or "",
            tenant_id=ctx.tenant_id or "default",
            action="admin.prompt_upsert",
            resource=f"prompt:{name}",
            detail={"version": rec.get("version")},
            result="ok",
        )
    return rec


@router.post("/{name}/publish")
async def publish_prompt(name: str, request: Request) -> dict[str, Any]:
    ctx = admin_ctx(request)
    require_permission(ctx, "admin:prompts")
    registry = request.app.state.prompt_registry
    try:
        rec = await _maybe_await(registry.publish(name))
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "prompt_not_found", "message": f"prompt {name} not found"},
        ) from exc
    audit = getattr(request.app.state, "audit", None)
    if audit is not None:
        await audit.log(
            user_id=ctx.user_id or "",
            tenant_id=ctx.tenant_id or "default",
            action="admin.prompt_publish",
            resource=f"prompt:{name}",
            detail={"version": rec.get("version")},
            result="ok",
        )
    return rec
