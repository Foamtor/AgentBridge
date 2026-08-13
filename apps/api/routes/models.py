"""Operator-managed model aliases and safe console model selection metadata."""

from __future__ import annotations

import os
from typing import Literal
from urllib.parse import urlparse

from admin.model_config_service import ModelConfigError
from config.model_config_env import (
    ModelConfigEnvFileError,
    generate_key,
    validate_key,
    write_key,
)
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from routes.admin_common import admin_ctx
from routes.admin_config_write import _same_origin, _verify_current_password

router = APIRouter(tags=["models"])


def normalize_model_alias(value: str) -> str:
    """Validate a user-facing model label while keeping URL-safe boundaries.

    The provider's model identifier belongs in ``model_name``.  The alias is a
    console-facing label, so it may use Unicode letters, spaces, and common
    punctuation without becoming an ambiguous URL path or database value.
    """
    if not isinstance(value, str) or not value or len(value) > 64:
        raise ValueError("alias must be 1 to 64 characters")
    if value != value.strip():
        raise ValueError("alias must not start or end with whitespace")
    if value.casefold() in {"default", "fast"}:
        raise ValueError("alias is reserved")
    if any(
        not (char.isalnum() or char in " _-.")
        for char in value
    ):
        raise ValueError(
            "alias may use letters, numbers, spaces, _, -, and . only"
        )
    return value


def _valid_model_alias(value: str) -> bool:
    try:
        normalize_model_alias(value)
    except ValueError:
        return False
    return True


def _validate_api_base(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError("api_base must be an absolute HTTP(S) URL")
    return value.rstrip("/")


class ModelCreateBody(BaseModel):
    alias: str = Field(min_length=1, max_length=64)
    provider: Literal["openai_compatible"] = "openai_compatible"
    api_base: str = Field(min_length=8, max_length=1024)
    model_name: str = Field(min_length=1, max_length=256)
    api_key: str = Field(min_length=1, max_length=4096)
    temperature: float = Field(default=0, ge=0, le=2)
    enabled: bool = True

    @field_validator("alias")
    @classmethod
    def validate_alias(cls, value: str) -> str:
        return normalize_model_alias(value)

    @field_validator("api_base")
    @classmethod
    def validate_api_base(cls, value: str) -> str:
        return _validate_api_base(value)


class ModelUpdateBody(BaseModel):
    api_base: str = Field(min_length=8, max_length=1024)
    model_name: str = Field(min_length=1, max_length=256)
    api_key: str | None = Field(default=None, max_length=4096)
    temperature: float = Field(default=0, ge=0, le=2)
    enabled: bool = True

    @field_validator("api_base")
    @classmethod
    def validate_api_base(cls, value: str) -> str:
        return _validate_api_base(value)


class ModelEncryptionKeyBody(BaseModel):
    encryption_key: str | None = Field(default=None, min_length=1, max_length=256)
    current_password: str | None = Field(default=None, min_length=1, max_length=256)


def _service(request: Request):
    return request.app.state.model_config_service


def _key_setup_available() -> bool:
    # A container-local .env disappears with the container unless an operator
    # explicitly points this setting at a persistent mounted file.
    return not os.path.exists("/.dockerenv") or bool(os.getenv("MODEL_CONFIG_ENV_FILE", "").strip())


def _require_model_admin(request: Request) -> str:
    ctx = admin_ctx(request)
    if "*" not in ctx.permissions and "admin:config" not in ctx.permissions:
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": "missing admin:config"},
        )
    return ctx.user_id or ""


def _raise_model_error(exc: ModelConfigError) -> None:
    code = str(exc)
    status_code = {
        "model_alias_exists": 409,
        "model_not_found": 404,
        "model_config_encryption_key_required": 503,
        "model_config_encryption_key_invalid": 503,
        "model_disabled": 409,
    }.get(code, 422)
    raise HTTPException(status_code=status_code, detail={"code": code}) from exc


@router.get("/models")
async def list_selectable_models(request: Request) -> dict:
    service = _service(request)
    managed = await service.list_public()
    selectable = service.selectable_base(
        default_model=request.app.state.settings.llm_model
    )
    selectable.extend(
        {
            "alias": item["alias"],
            "model_name": item["model_name"],
            "kind": "real",
            "last_test_status": item["last_test_status"],
            "last_tested_at": item["last_tested_at"],
            "last_test_capability": item["last_test_capability"],
        }
        for item in managed
        if item["enabled"] and item["runtime_ready"]
    )
    return {
        "models": selectable
    }


@router.get("/admin/models")
async def list_models(request: Request) -> dict:
    _require_model_admin(request)
    return {
        "models": await _service(request).list_public(),
        "encryption_ready": _service(request).encryption_ready,
        "key_setup_available": _key_setup_available(),
    }


@router.put("/admin/models/encryption-key")
async def save_model_encryption_key(body: ModelEncryptionKeyBody, request: Request) -> dict:
    """Generate or persist the deployment key without returning its value."""
    _same_origin(request)
    actor = _require_model_admin(request)
    service = _service(request)
    if service.encryption_ready:
        raise HTTPException(status_code=409, detail={"code": "model_config_encryption_key_already_configured"})
    if not _key_setup_available():
        raise HTTPException(status_code=409, detail={"code": "model_config_env_file_deployment_managed"})
    if request.app.state.settings.resolved_auth_mode == "disabled":
        raise HTTPException(status_code=409, detail={"code": "reauth_required"})
    verified_username = await _verify_current_password(request, body.model_dump())
    key = generate_key() if body.encryption_key is None else body.encryption_key
    try:
        write_key(request.app.state.settings.model_config_env_file, validate_key(key))
        await service.configure_encryption_key(key)
    except ModelConfigEnvFileError as exc:
        raise HTTPException(status_code=422, detail={"code": str(exc)}) from exc
    except ModelConfigError as exc:
        _raise_model_error(exc)
    audit = getattr(request.app.state, "audit", None)
    if audit is not None:
        await audit.log(
            user_id=verified_username or actor,
            tenant_id="default",
            action="admin.model_encryption_key_write",
            resource="deployment:.env",
            detail={"generated": body.encryption_key is None},
            result="ok",
        )
    return {"configured": True, "runtime_ready": True, "restart_required": True}


@router.post("/admin/models", status_code=status.HTTP_201_CREATED)
async def create_model(body: ModelCreateBody, request: Request) -> dict:
    actor = _require_model_admin(request)
    try:
        model = await _service(request).create(body.model_dump(), actor=actor)
    except ModelConfigError as exc:
        _raise_model_error(exc)
    await request.app.state.audit.log(
        user_id=actor, tenant_id="default", action="admin.model_create",
        resource=f"model:{body.alias}", detail={"model_name": body.model_name}, result="ok",
    )
    return model


@router.post("/admin/models/{alias}/test")
async def test_model(alias: str, request: Request) -> dict:
    actor = _require_model_admin(request)
    if not _valid_model_alias(alias):
        raise HTTPException(status_code=404, detail={"code": "model_not_found"})
    try:
        result = await _service(request).test_connection(alias)
    except ModelConfigError as exc:
        code = str(exc)
        if code in {
            "model_connection_test_failed",
            "model_connection_test_timeout",
            "model_tool_call_test_failed",
            "model_tool_call_test_timeout",
        }:
            await request.app.state.audit.log(
                user_id=actor, tenant_id="default", action="admin.model_connection_test",
                resource=f"model:{alias}", detail={"code": code}, result="failed",
            )
            detail = {"code": code}
            reason = getattr(exc, "reason", None)
            if reason:
                detail["reason"] = reason
            raise HTTPException(
                status_code=(
                    504
                    if code.endswith("timeout")
                    else 422
                    if code == "model_tool_call_test_failed"
                    else 502
                ),
                detail=detail,
            ) from exc
        _raise_model_error(exc)
    await request.app.state.audit.log(
        user_id=actor, tenant_id="default", action="admin.model_connection_test",
        resource=f"model:{alias}", detail={"latency_ms": result["latency_ms"]}, result="ok",
    )
    return result


@router.put("/admin/models/{alias}")
async def update_model(alias: str, body: ModelUpdateBody, request: Request) -> dict:
    actor = _require_model_admin(request)
    if not _valid_model_alias(alias):
        raise HTTPException(status_code=404, detail={"code": "model_not_found"})
    try:
        model = await _service(request).update(alias, body.model_dump())
    except ModelConfigError as exc:
        _raise_model_error(exc)
    await request.app.state.audit.log(
        user_id=actor, tenant_id="default", action="admin.model_update",
        resource=f"model:{alias}", detail={"model_name": body.model_name}, result="ok",
    )
    return model


@router.delete("/admin/models/{alias}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(alias: str, request: Request) -> None:
    actor = _require_model_admin(request)
    if not _valid_model_alias(alias):
        raise HTTPException(status_code=404, detail={"code": "model_not_found"})
    if not await _service(request).delete(alias):
        raise HTTPException(status_code=404, detail={"code": "model_not_found"})
    await request.app.state.audit.log(
        user_id=actor, tenant_id="default", action="admin.model_delete",
        resource=f"model:{alias}", detail={}, result="ok",
    )
