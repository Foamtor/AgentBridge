"""PUT /admin/config/{key} — tier-A hot config writes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from routes.admin_common import admin_ctx
from routes.admin_config import ConfigItemSpec, _CONFIG_MANIFEST, _require_config_read

router = APIRouter(prefix="/admin", tags=["admin"])

_TIER_A_MANIFEST: list[ConfigItemSpec] = [
    ConfigItemSpec("RATE_LIMIT_PER_MINUTE", "rate_limit_per_minute", "A", "每分钟限流"),
]


def _writable_spec(key: str) -> ConfigItemSpec | None:
    for spec in _TIER_A_MANIFEST:
        if spec.key == key:
            return spec
    return None


def _require_config_write(ctx) -> None:
    _require_config_read(ctx)
    if "*" in ctx.permissions or "admin:config" in ctx.permissions:
        return
    raise HTTPException(
        status_code=403,
        detail={"code": "forbidden", "message": "missing admin:config"},
    )


@router.put("/config/{key}")
async def put_config(key: str, request: Request, body: dict[str, Any]) -> dict[str, Any]:
    ctx = admin_ctx(request)
    _require_config_write(ctx)
    spec = _writable_spec(key)
    if spec is None:
        for item in _CONFIG_MANIFEST:
            if item.key == key and item.tier != "A":
                raise HTTPException(
                    status_code=400,
                    detail={"code": "config_not_writable", "message": f"{key} is not tier A"},
                )
        raise HTTPException(
            status_code=404,
            detail={"code": "config_not_found", "message": f"unknown config key {key}"},
        )
    if "value" not in body:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_body", "message": "value is required"},
        )
    provider = request.app.state.config_provider
    await provider.set(key, body["value"])
    settings = request.app.state.settings
    if hasattr(settings, spec.field):
        setattr(settings, spec.field, body["value"])
    audit = getattr(request.app.state, "audit", None)
    if audit is not None:
        await audit.log(
            user_id=ctx.user_id or "",
            tenant_id=ctx.tenant_id or "default",
            action="admin.config_write",
            resource=f"config:{key}",
            detail={"value": body["value"]},
            result="ok",
        )
    return {"key": key, "value": body["value"], "tier": "A"}
