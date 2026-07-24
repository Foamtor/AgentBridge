"""GET /threads and /threads/{id}/messages."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from auth.run_context import claims_to_run_context

router = APIRouter(prefix="/threads", tags=["threads"])


def _ctx(request: Request):
    settings = request.app.state.settings
    claims = getattr(request.state, "auth_claims", None)
    return claims_to_run_context(claims, auth_required=settings.auth_required)


@router.get("/")
async def list_threads(request: Request) -> list[dict[str, Any]]:
    ctx = _ctx(request)
    runs = await request.app.state.run_store.list_by_tenant(ctx.tenant_id)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for run in runs:
        tid = str(run.get("thread_id") or "")
        if not tid or tid in seen:
            continue
        seen.add(tid)
        out.append({"thread_id": tid, "tenant_id": ctx.tenant_id})
    return out


@router.get("/{thread_id}/messages")
async def list_messages(thread_id: str, request: Request) -> list[dict[str, Any]]:
    ctx = _ctx(request)
    return await request.app.state.message_store.list_messages(ctx.tenant_id, thread_id)
