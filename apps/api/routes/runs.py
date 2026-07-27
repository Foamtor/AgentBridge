"""GET /runs/{id} and /runs/{id}/events."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from agentbridge_core.application.replay import replay_run
from auth.run_context import claims_to_run_context

router = APIRouter(prefix="/runs", tags=["runs"])


def _ctx(request: Request):
    settings = request.app.state.settings
    claims = getattr(request.state, "auth_claims", None)
    return claims_to_run_context(
        claims,
        auth_required=settings.auth_required,
        policy_bundle_version=settings.policy_bundle_version,
    )


@router.get("/{run_id}")
async def get_run(run_id: str, request: Request) -> dict[str, Any]:
    ctx = _ctx(request)
    tenant_id = ctx.tenant_id or "default"
    run = await request.app.state.run_store.get(run_id, tenant_id=tenant_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "run_not_found", "message": "run not found"},
        )
    return run


@router.get("/{run_id}/events")
async def get_run_events(run_id: str, request: Request) -> list[dict[str, Any]]:
    ctx = _ctx(request)
    tenant_id = ctx.tenant_id or "default"
    run = await request.app.state.run_store.get(run_id, tenant_id=tenant_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "run_not_found", "message": "run not found"},
        )
    return await replay_run(
        request.app.state.event_log, run_id, tenant_id=tenant_id
    )
