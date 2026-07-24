"""Admin APIs — domains list and audit export (RBAC)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from auth.rbac import require_permission
from auth.run_context import claims_to_run_context

router = APIRouter(prefix="/admin", tags=["admin"])

# Strip likely user/prompt payload keys from audit detail on export.
_REDACT_DETAIL_KEYS = frozenset(
    {
        "query",
        "content",
        "message",
        "prompt",
        "text",
        "input",
        "output",
        "body",
        "messages",
    }
)


def _ctx(request: Request):
    settings = request.app.state.settings
    claims = getattr(request.state, "auth_claims", None)
    return claims_to_run_context(
        claims,
        auth_required=settings.auth_required,
        policy_bundle_version=settings.policy_bundle_version,
    )


def _sanitize_record(rec: dict[str, Any]) -> dict[str, Any]:
    detail = rec.get("detail")
    if isinstance(detail, dict):
        detail = {k: v for k, v in detail.items() if k not in _REDACT_DETAIL_KEYS}
    else:
        detail = {}
    return {
        "user_id": rec.get("user_id", ""),
        "tenant_id": rec.get("tenant_id", ""),
        "action": rec.get("action", ""),
        "resource": rec.get("resource", ""),
        "result": rec.get("result", ""),
        "detail": detail,
    }


@router.get("/domains")
async def list_domains(request: Request) -> list[dict[str, Any]]:
    ctx = _ctx(request)
    require_permission(ctx, "admin:domains")
    names = request.app.state.tools.keys()
    return [{"name": n, "kind": "domain"} for n in names]


@router.get("/audit/export")
async def export_audit(request: Request) -> StreamingResponse:
    """JSONL audit export without large user-text fields."""
    ctx = _ctx(request)
    require_permission(ctx, "admin:audit")
    records = list(getattr(request.app.state.audit, "records", []) or [])

    async def lines():
        for rec in records:
            yield json.dumps(_sanitize_record(rec), ensure_ascii=False) + "\n"

    return StreamingResponse(
        lines(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="audit.jsonl"'},
    )
