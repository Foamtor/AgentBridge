"""GET /admin/knowledge/status — knowledge backend status."""

from __future__ import annotations

from typing import Any, Protocol

from fastapi import APIRouter, HTTPException, Request

from auth.rbac import require_permission
from routes.admin_common import admin_ctx

router = APIRouter(prefix="/admin", tags=["admin"])


class KnowledgeStatusProvider(Protocol):
    async def get_status(self, *, tenant_id: str) -> dict[str, Any]: ...


@router.get("/knowledge/status")
async def knowledge_status(request: Request) -> dict[str, Any]:
    ctx = admin_ctx(request)
    require_permission(ctx, "admin:knowledge")
    provider = getattr(request.app.state, "knowledge_status_provider", None)
    if provider is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "blocked_by_base_r_b_status_api",
                "message": "knowledge status provider is not ready",
            },
        )
    tenant_id = ctx.tenant_id or "default"
    return await provider.get_status(tenant_id=tenant_id)
