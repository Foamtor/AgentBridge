"""GET /admin/overview — C0 aggregate dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Request

from auth.rbac import require_permission
from routes.admin_common import admin_ctx
from routes.ready import (
    _check_checkpointer,
    _check_data_source,
    _check_event_log,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _count_domains(catalog: list[dict[str, Any]]) -> dict[str, int]:
    registered = len(catalog)
    graph_ready = sum(1 for item in catalog if item.get("graph_registered"))
    return {"registered": registered, "graph_ready": graph_ready}


def _runs_24h_stats(runs: list[dict[str, Any]]) -> dict[str, int]:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    total = 0
    errors = 0
    for run in runs:
        started = _parse_iso(str(run.get("started_at") or ""))
        if started is None or started < since:
            continue
        total += 1
        if run.get("status") in {"error", "cancelled"}:
            errors += 1
    return {"total": total, "errors": errors}


def _recent_failed_runs(
    runs: list[dict[str, Any]], *, limit: int = 5
) -> list[dict[str, Any]]:
    failed = [r for r in runs if r.get("status") in {"error", "cancelled"}]
    failed.sort(key=lambda r: str(r.get("started_at") or ""), reverse=True)
    out: list[dict[str, Any]] = []
    for run in failed[:limit]:
        out.append(
            {
                "run_id": run.get("run_id"),
                "route": run.get("route", ""),
                "status": run.get("status"),
                "started_at": run.get("started_at"),
            }
        )
    return out


async def _ready_snapshot(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    checks = {
        "checkpointer": await _check_checkpointer(
            getattr(request.app.state, "checkpointers", None)
        ),
        "event_log": await _check_event_log(
            getattr(request.app.state, "event_log", None)
        ),
        "data_source": await _check_data_source(
            getattr(request.app.state, "data_source", None),
            enabled=bool(settings.enable_data_source),
        ),
    }
    failed = [k for k, v in checks.items() if v.get("status") == "fail"]
    return {"status": "not_ready" if failed else "ready", "checks": checks}


def _knowledge_backend_status(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    backend_type = settings.knowledge_backend
    if backend_type == "fake":
        return {"type": backend_type, "status": "skipped"}
    retriever = getattr(request.app.state, "retriever", None)
    if retriever is None:
        return {
            "type": backend_type,
            "status": "degraded",
            "message": "retriever not configured",
        }
    return {"type": backend_type, "status": "ok"}


@router.get("/overview")
async def overview(request: Request) -> dict[str, Any]:
    ctx = admin_ctx(request)
    require_permission(ctx, "admin:read")
    tenant_id = ctx.tenant_id or "default"
    runs = await request.app.state.run_store.list_by_tenant(tenant_id)
    catalog = getattr(request.app.state, "domain_catalog", None) or []
    settings = request.app.state.settings
    return {
        "domains": _count_domains(catalog),
        "llm_backend": {"type": settings.llm_backend, "status": "ok"},
        "knowledge_backend": _knowledge_backend_status(request),
        "infra_ready": await _ready_snapshot(request),
        "runs_24h": _runs_24h_stats(runs),
        "recent_failed_runs": _recent_failed_runs(runs),
    }
