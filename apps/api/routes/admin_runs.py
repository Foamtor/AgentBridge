"""GET /admin/runs — tenant-scoped run list with filters."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, Request

from auth.rbac import require_permission
from routes.admin_common import admin_ctx

router = APIRouter(prefix="/admin", tags=["admin"])


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _filter_runs(
    runs: list[dict[str, Any]],
    *,
    status: str | None,
    route: str | None,
    since: str | None,
    until: str | None,
) -> list[dict[str, Any]]:
    since_dt = _parse_iso(since)
    until_dt = _parse_iso(until)
    out: list[dict[str, Any]] = []
    for run in runs:
        if status and run.get("status") != status:
            continue
        if route and run.get("route") != route:
            continue
        started = _parse_iso(str(run.get("started_at") or ""))
        if since_dt and (started is None or started < since_dt):
            continue
        if until_dt and (started is None or started > until_dt):
            continue
        out.append(run)
    out.sort(key=lambda r: str(r.get("started_at") or ""), reverse=True)
    return out


def _project_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run.get("run_id"),
        "thread_id": run.get("thread_id"),
        "route": run.get("route"),
        "status": run.get("status"),
        "tenant_id": run.get("tenant_id"),
        "started_at": run.get("started_at"),
        "ended_at": run.get("ended_at"),
    }


@router.get("/runs")
async def list_runs(
    request: Request,
    status: str | None = None,
    route: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
) -> dict[str, Any]:
    ctx = admin_ctx(request)
    require_permission(ctx, "admin:read")
    tenant_id = ctx.tenant_id or "default"
    runs = await request.app.state.run_store.list_by_tenant(tenant_id)
    filtered = _filter_runs(
        runs, status=status, route=route, since=since, until=until
    )
    if cursor:
        filtered = [r for r in filtered if str(r.get("run_id") or "") < cursor]
    page = filtered[: limit + 1]
    items = [_project_run(r) for r in page[:limit]]
    next_cursor = page[limit]["run_id"] if len(page) > limit else None
    return {"items": items, "next_cursor": next_cursor}
