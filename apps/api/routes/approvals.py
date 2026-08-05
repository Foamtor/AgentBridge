"""POST /approvals/{id} — resolve HIL (permission approval:decide)."""

from __future__ import annotations

from typing import Any, Literal

from agentbridge_core.application.errors import RunNotFound, ThreadBusy
from agentbridge_core.errors import ApprovalStateConflict
from auth.run_context import claims_to_run_context
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalDecisionBody(BaseModel):
    decision: Literal["approve", "deny"]


class ApprovalPublic(BaseModel):
    approval_id: str
    status: str
    decision: str | None = None
    reason: str | None = None
    run_id: str | None = None
    thread_id: str | None = None
    result: dict[str, Any] | None = None


class ApprovalDecisionResponse(BaseModel):
    ok: Literal[True] = True
    approval: ApprovalPublic


@router.get(
    "/{approval_id}",
    response_model=ApprovalDecisionResponse,
    response_model_exclude_none=True,
)
async def get_approval(approval_id: str, request: Request) -> ApprovalDecisionResponse:
    ctx = _ctx(request)
    tenant_id = ctx.tenant_id or "default"
    record = await request.app.state.approval_store.get(
        approval_id, tenant_id=tenant_id
    )
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "approval_not_found", "message": "approval not found"},
        )
    requester = record.get("requester_context") or {}
    requester_id = str(requester.get("user_id") or "")
    may_decide = "approval:decide" in ctx.permissions or "*" in ctx.permissions
    if not may_decide and requester_id != ctx.user_id:
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": "approval access denied"},
        )
    return ApprovalDecisionResponse(approval=ApprovalPublic.model_validate(record))


def _ctx(request: Request):
    settings = request.app.state.settings
    claims = getattr(request.state, "auth_claims", None)
    return claims_to_run_context(
        claims,
        auth_required=settings.auth_required,
        policy_bundle_version=settings.policy_bundle_version,
    )


@router.post(
    "/{approval_id}",
    response_model=ApprovalDecisionResponse,
    response_model_exclude_none=True,
)
async def resolve_approval(
    approval_id: str, body: ApprovalDecisionBody, request: Request
) -> ApprovalDecisionResponse:
    ctx = _ctx(request)
    if "approval:decide" not in ctx.permissions and "*" not in ctx.permissions:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "forbidden",
                "message": "missing permission approval:decide",
            },
        )
    tenant_id = ctx.tenant_id or "default"
    lifecycle = request.app.state.run_lifecycle
    try:
        rec = await lifecycle.finalize_approval(
            approval_id=approval_id,
            tenant_id=tenant_id,
            decision=body.decision,
            sink=None,
            approver_ctx=ctx,
        )
    except RunNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "approval_not_found", "message": "approval not found"},
        ) from exc
    except ThreadBusy as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "thread_busy",
                "message": "cannot resume; lock held",
            },
        ) from exc
    except ApprovalStateConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "approval_state_conflict",
                "message": "approval is executing",
            },
        ) from exc
    return ApprovalDecisionResponse(
        approval=ApprovalPublic.model_validate(rec)
    )
