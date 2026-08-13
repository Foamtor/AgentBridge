"""GET /admin/knowledge/status — knowledge backend status."""

from __future__ import annotations

from typing import Any, Protocol

from auth.rbac import require_permission
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from routes.admin_common import admin_ctx

router = APIRouter(prefix="/admin", tags=["admin"])


class KnowledgeStatusProvider(Protocol):
    async def get_status(self, *, tenant_id: str) -> dict[str, Any]: ...


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=5, ge=1, le=20)


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


@router.post("/knowledge/search")
async def search_knowledge(
    body: KnowledgeSearchRequest, request: Request
) -> dict[str, Any]:
    """Run a tenant-scoped retrieval probe for console operators."""
    ctx = admin_ctx(request)
    require_permission(ctx, "admin:knowledge")
    tenant_id = ctx.tenant_id or "default"
    try:
        raw_hits = await request.app.state.retriever.similarity_search(
            body.query, tenant_id=tenant_id, k=body.limit
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "knowledge_search_unavailable",
                "message": "knowledge search is unavailable",
            },
        ) from exc
    hits: list[dict[str, Any]] = []
    for hit in raw_hits:
        if not isinstance(hit, dict) or hit.get("tenant_id") != tenant_id:
            continue
        hits.append(
            {
                "chunk_id": str(hit.get("chunk_id") or ""),
                "doc_id": str(hit.get("doc_id") or ""),
                "text": str(hit.get("text") or ""),
                "score": hit.get("score"),
                "metadata": dict(hit.get("metadata") or {}),
            }
        )
    return {"query": body.query, "hits": hits}
