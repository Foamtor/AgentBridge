"""Shared helpers for admin routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, Request

from agentbridge_core.protocol.context import RunContext
from auth.run_context import claims_to_run_context


def admin_ctx(request: Request):
    settings = request.app.state.settings
    claims = getattr(request.state, "auth_claims", None)
    return claims_to_run_context(
        claims,
        auth_required=settings.auth_required,
        policy_bundle_version=settings.policy_bundle_version,
    )


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def require_tools_read(ctx: RunContext) -> None:
    if "*" in ctx.permissions or "admin:tools" in ctx.permissions:
        return
    if "admin:read" in ctx.permissions:
        return
    raise HTTPException(
        status_code=403,
        detail={"code": "forbidden", "message": "missing admin:tools or admin:read"},
    )
