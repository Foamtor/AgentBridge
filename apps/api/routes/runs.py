"""GET /runs/{id} and /runs/{id}/events."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agentbridge_core.application.replay import replay_run
from auth.run_context import claims_to_run_context
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from observability.run_diagnostics import build_run_diagnostics
from pydantic import BaseModel, Field

router = APIRouter(prefix="/runs", tags=["runs"])


class AnnotationRequest(BaseModel):
    category: str = Field(default="note", pattern=r"^(note|badcase)$")
    rating: str = Field(default="neutral", pattern=r"^(positive|negative|neutral)$")
    reason: str = Field(min_length=1, max_length=2000)
    expected_behavior: str = Field(default="", max_length=4000)
    tags: list[str] = Field(default_factory=list, max_length=20)


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


async def _require_run(run_id: str, request: Request) -> tuple[Any, str, dict[str, Any]]:
    ctx = _ctx(request)
    tenant_id = ctx.tenant_id or "default"
    run = await request.app.state.run_store.get(run_id, tenant_id=tenant_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "run_not_found", "message": "run not found"},
        )
    return ctx, tenant_id, run


@router.get("/{run_id}/diagnostics")
async def get_run_diagnostics(run_id: str, request: Request) -> dict[str, Any]:
    _, tenant_id, _ = await _require_run(run_id, request)
    events = await replay_run(request.app.state.event_log, run_id, tenant_id=tenant_id)
    return build_run_diagnostics(events)


@router.get("/{run_id}/events.jsonl")
async def export_run_events(run_id: str, request: Request) -> Response:
    _, tenant_id, _ = await _require_run(run_id, request)
    events = await replay_run(request.app.state.event_log, run_id, tenant_id=tenant_id)
    body = "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events)
    return Response(
        content=body,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{run_id}.jsonl"'},
    )


@router.get("/{run_id}/annotations")
async def list_run_annotations(run_id: str, request: Request) -> list[dict[str, Any]]:
    _, tenant_id, _ = await _require_run(run_id, request)
    return await request.app.state.run_annotation_store.list_for_run(tenant_id, run_id)


@router.post("/{run_id}/annotations", status_code=201)
async def create_run_annotation(
    run_id: str, body: AnnotationRequest, request: Request
) -> dict[str, Any]:
    ctx, tenant_id, _ = await _require_run(run_id, request)
    annotation = await request.app.state.run_annotation_store.create(
        {
            "annotation_id": f"ann-{uuid4().hex}",
            "tenant_id": tenant_id,
            "run_id": run_id,
            "author_id": ctx.user_id,
            "category": body.category,
            "rating": body.rating,
            "reason": body.reason,
            "expected_behavior": body.expected_behavior,
            "tags": list(dict.fromkeys(tag.strip() for tag in body.tags if tag.strip())),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    await request.app.state.audit.log(
        user_id=ctx.user_id or "anonymous",
        tenant_id=tenant_id,
        action="console.run_annotation_create",
        resource=f"run:{run_id}",
        detail={
            "annotation_id": annotation["annotation_id"],
            "category": annotation["category"],
            "rating": annotation["rating"],
        },
        result="ok",
    )
    return annotation


@router.delete("/{run_id}/annotations/{annotation_id}", status_code=204)
async def delete_run_annotation(
    run_id: str, annotation_id: str, request: Request
) -> Response:
    ctx, tenant_id, _ = await _require_run(run_id, request)
    deleted = await request.app.state.run_annotation_store.delete(tenant_id, annotation_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={"code": "annotation_not_found", "message": "annotation not found"},
        )
    await request.app.state.audit.log(
        user_id=ctx.user_id or "anonymous",
        tenant_id=tenant_id,
        action="console.run_annotation_delete",
        resource=f"run:{run_id}",
        detail={"annotation_id": annotation_id},
        result="ok",
    )
    return Response(status_code=204)
