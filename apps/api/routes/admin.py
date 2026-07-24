"""GET /admin/domains — requires admin:domains (or *)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from auth.rbac import require_permission
from auth.run_context import claims_to_run_context

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/domains")
async def list_domains(request: Request) -> list[dict[str, Any]]:
    settings = request.app.state.settings
    claims = getattr(request.state, "auth_claims", None)
    ctx = claims_to_run_context(claims, auth_required=settings.auth_required)
    require_permission(ctx, "admin:domains")
    names = request.app.state.tools.keys()
    return [{"name": n, "kind": "domain"} for n in names]
