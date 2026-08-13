"""Admin APIs — domains list and audit export (RBAC)."""

from __future__ import annotations

import json
from typing import Any

from auth.rbac import require_permission
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from routes.admin_common import admin_ctx

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
    return admin_ctx(request)


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
async def list_domains(request: Request) -> dict[str, Any]:
    ctx = _ctx(request)
    require_permission(ctx, "admin:domains")
    catalog = getattr(request.app.state, "domain_catalog", None) or []
    return {"domains": catalog}


@router.get("/audit/export")
async def export_audit(request: Request) -> StreamingResponse:
    """JSONL audit export without large user-text fields."""
    ctx = _ctx(request)
    require_permission(ctx, "admin:audit")
    audit = request.app.state.audit
    list_records = getattr(audit, "list_records", None)
    if callable(list_records):
        records = await list_records(tenant_id=ctx.tenant_id or "default")
    else:
        records = list(getattr(audit, "records", []) or [])

    async def lines():
        for rec in records:
            yield json.dumps(_sanitize_record(rec), ensure_ascii=False) + "\n"

    return StreamingResponse(
        lines(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="audit.jsonl"'},
    )
