"""PUT /admin/config/{key} — tier-A hot config writes."""

from __future__ import annotations

from typing import Any

from auth.local_admin import AuthSessionError
from fastapi import APIRouter, HTTPException, Request

from routes.admin_common import admin_ctx
from routes.admin_config import (
    _CONFIG_MANIFEST,
    ConfigItemSpec,
    _require_config_read,
    runtime_config_source,
)

router = APIRouter(prefix="/admin", tags=["admin"])

_TIER_A_MANIFEST: list[ConfigItemSpec] = [
    ConfigItemSpec("RATE_LIMIT_PER_MINUTE", "rate_limit_per_minute", "A", "每分钟限流"),
    ConfigItemSpec("ADMIN_TOOL_INVOKE_ENABLED", "admin_tool_invoke_enabled", "A", "允许管理员试运行工具"),
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


def _same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        return
    expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
    if origin != expected:
        raise HTTPException(status_code=403, detail={"code": "cross_site_request"})


def _validated_value(key: str, value: Any) -> Any:
    if key == "RATE_LIMIT_PER_MINUTE":
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100000:
            raise HTTPException(status_code=422, detail={"code": "invalid_config_value", "message": "RATE_LIMIT_PER_MINUTE must be an integer from 0 to 100000"})
        return value
    if key == "ADMIN_TOOL_INVOKE_ENABLED":
        if not isinstance(value, bool):
            raise HTTPException(status_code=422, detail={"code": "invalid_config_value", "message": "ADMIN_TOOL_INVOKE_ENABLED must be a boolean"})
        return value
    raise HTTPException(status_code=400, detail={"code": "config_not_writable"})


async def _verify_current_password(request: Request, body: dict[str, Any]) -> str | None:
    mode = request.app.state.settings.resolved_auth_mode
    if mode == "disabled":
        return None
    if mode != "local":
        raise HTTPException(status_code=409, detail={"code": "reauth_not_supported", "message": "configuration writes require an external identity reauthentication flow"})
    password = body.get("current_password")
    if not isinstance(password, str) or not password:
        raise HTTPException(status_code=401, detail={"code": "current_password_required"})
    service = getattr(request.app.state, "console_auth_service", None)
    if service is None:
        raise HTTPException(status_code=404, detail={"code": "auth_unavailable"})
    token = str(request.cookies.get(request.app.state.settings.auth_cookie_name) or "")
    try:
        return await service.verify_reauthentication(session_token=token, password=password)
    except AuthSessionError as exc:
        status = 429 if str(exc) == "auth_rate_limited" else 401
        raise HTTPException(status_code=status, detail={"code": str(exc)}) from exc


@router.put("/config/{key}")
async def put_config(key: str, request: Request, body: dict[str, Any]) -> dict[str, Any]:
    _same_origin(request)
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
    value = _validated_value(key, body["value"])
    verified_username = await _verify_current_password(request, body)
    provider = request.app.state.config_provider
    await provider.set(key, value, updated_by=verified_username or ctx.user_id or "admin")
    settings = request.app.state.settings
    if hasattr(settings, spec.field):
        setattr(settings, spec.field, value)
    audit = getattr(request.app.state, "audit", None)
    if audit is not None:
        await audit.log(
            user_id=ctx.user_id or "",
            tenant_id=ctx.tenant_id or "default",
            action="admin.config_write",
            resource=f"config:{key}",
            detail={"value": value},
            result="ok",
        )
    return {
        "key": key,
        "value": value,
        "tier": "A",
        "source": runtime_config_source(settings),
    }
