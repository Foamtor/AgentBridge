"""POST /approvals/{id} — resolve HIL (permission approval:decide)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from agentbridge_core.application.errors import RunNotFound, ThreadBusy
from auth.run_context import claims_to_run_context

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalDecisionBody(BaseModel):
    decision: Literal["approve", "deny"]


def _ctx(request: Request):
    settings = request.app.state.settings
    claims = getattr(request.state, "auth_claims", None)
    return claims_to_run_context(
        claims,
        auth_required=settings.auth_required,
        policy_bundle_version=settings.policy_bundle_version,
    )


@router.post("/{approval_id}")
async def resolve_approval(
    approval_id: str, body: ApprovalDecisionBody, request: Request
) -> dict[str, Any]:
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
    return {"ok": True, "approval": rec}
