"""Operator-managed model aliases and safe console model selection metadata."""

from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from admin.model_config_service import ModelConfigError
from routes.admin_common import admin_ctx

router = APIRouter(tags=["models"])
_ALIAS = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


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
        if not _ALIAS.fullmatch(value):
            raise ValueError("alias must be lowercase letters, digits, _ or -")
        if value in {"default", "fast"}:
            raise ValueError("alias is reserved")
        return value

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


def _service(request: Request):
    return request.app.state.model_config_service


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
        {"alias": item["alias"], "model_name": item["model_name"], "kind": "real"}
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
    }


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


@router.put("/admin/models/{alias}")
async def update_model(alias: str, body: ModelUpdateBody, request: Request) -> dict:
    actor = _require_model_admin(request)
    if not _ALIAS.fullmatch(alias) or alias in {"default", "fast"}:
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
    if not _ALIAS.fullmatch(alias) or alias in {"default", "fast"}:
        raise HTTPException(status_code=404, detail={"code": "model_not_found"})
    if not await _service(request).delete(alias):
        raise HTTPException(status_code=404, detail={"code": "model_not_found"})
    await request.app.state.audit.log(
        user_id=actor, tenant_id="default", action="admin.model_delete",
        resource=f"model:{alias}", detail={}, result="ok",
    )
