"""GET /admin/usage/tokens — token usage aggregation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from auth.rbac import require_permission
from routes.admin_common import admin_ctx

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/usage/tokens")
async def usage_tokens(
    request: Request,
    group_by: str = "route",
    since: str | None = None,
    until: str | None = None,
) -> dict[str, Any]:
    ctx = admin_ctx(request)
    require_permission(ctx, "admin:usage")
    if group_by not in {"tenant", "route", "model"}:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_group_by", "message": "group_by must be tenant|route|model"},
        )
    usage_store = request.app.state.usage_store
    return usage_store.aggregate(group_by=group_by, since=since, until=until)
