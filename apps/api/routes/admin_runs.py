"""GET /admin/runs — tenant-scoped run list with filters."""

from __future__ import annotations

import base64
from typing import Any

from auth.rbac import require_permission
from fastapi import APIRouter, Query, Request
from observability.run_diagnostics import build_run_diagnostics

from routes.admin_common import admin_ctx, parse_iso

router = APIRouter(prefix="/admin", tags=["admin"])

_CURSOR_SEP = "|"


def _run_sort_key(run: dict[str, Any]) -> tuple[str, str]:
    return (str(run.get("started_at") or ""), str(run.get("run_id") or ""))


def _encode_cursor(run: dict[str, Any]) -> str:
    started_at, run_id = _run_sort_key(run)
    raw = f"{started_at}{_CURSOR_SEP}{run_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[str, str] | None:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    except (ValueError, UnicodeDecodeError):
        return None
    if _CURSOR_SEP not in raw:
        return None
    started_at, run_id = raw.split(_CURSOR_SEP, 1)
    return started_at, run_id


def _before_cursor(run: dict[str, Any], cursor_started: str, cursor_run_id: str) -> bool:
    started_at, run_id = _run_sort_key(run)
    if started_at < cursor_started:
        return True
    return started_at == cursor_started and run_id < cursor_run_id


def _filter_runs(
    runs: list[dict[str, Any]],
    *,
    status: str | None,
    route: str | None,
    since: str | None,
    until: str | None,
) -> list[dict[str, Any]]:
    since_dt = parse_iso(since)
    until_dt = parse_iso(until)
    out: list[dict[str, Any]] = []
    for run in runs:
        if status and run.get("status") != status:
            continue
        if route and run.get("route") != route:
            continue
        started = parse_iso(str(run.get("started_at") or ""))
        if since_dt and (started is None or started < since_dt):
            continue
        if until_dt and (started is None or started > until_dt):
            continue
        out.append(run)
    out.sort(key=_run_sort_key, reverse=True)
    return out


def _project_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run.get("run_id"),
        "thread_id": run.get("thread_id"),
        "route": run.get("route"),
        "trace_id": run.get("trace_id"),
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
    thread_id: str | None = None,
    trace_id: str | None = None,
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
    if thread_id:
        filtered = [run for run in filtered if run.get("thread_id") == thread_id]
    if trace_id:
        filtered = [run for run in filtered if run.get("trace_id") == trace_id]
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded is not None:
            cursor_started, cursor_run_id = decoded
            filtered = [
                r
                for r in filtered
                if _before_cursor(r, cursor_started, cursor_run_id)
            ]
    page = filtered[: limit + 1]
    items = [_project_run(r) for r in page[:limit]]
    next_cursor = _encode_cursor(page[limit]) if len(page) > limit else None
    return {"items": items, "next_cursor": next_cursor}


@router.get("/diagnostics")
async def aggregate_diagnostics(request: Request) -> dict[str, Any]:
    ctx = admin_ctx(request)
    require_permission(ctx, "admin:read")
    tenant_id = ctx.tenant_id or "default"
    runs = await request.app.state.run_store.list_by_tenant(tenant_id)
    annotations = await request.app.state.run_annotation_store.list_for_tenant(
        tenant_id
    )
    by_route: dict[str, dict[str, int]] = {}
    tool_usage: dict[str, int] = {}
    contract_failures = 0
    for run in runs:
        run_id = str(run.get("run_id") or "")
        route = str(run.get("route") or "unknown")
        route_stats = by_route.setdefault(route, {"runs": 0, "failures": 0})
        route_stats["runs"] += 1
        if run.get("status") in {"error", "cancelled"}:
            route_stats["failures"] += 1
        if not run_id:
            continue
        events = await request.app.state.event_log.list(run_id, tenant_id=tenant_id)
        diagnostics = build_run_diagnostics(events)
        if not diagnostics["contract_ok"]:
            contract_failures += 1
        for tool in diagnostics["tools"]:
            name = str(tool.get("name") or "unknown")
            tool_usage[name] = tool_usage.get(name, 0) + 1
    return {
        "total_runs": len(runs),
        "contract_failures": contract_failures,
        "annotations": len(annotations),
        "badcases": sum(1 for item in annotations if item.get("category") == "badcase"),
        "by_route": by_route,
        "tool_usage": tool_usage,
    }
