"""GET /ready — skip checks for disabled deps; fail only if enabled and broken."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["ops"])


async def _check_data_source(ds: Any, *, enabled: bool) -> dict[str, Any]:
    if not enabled:
        return {"status": "skipped", "reason": "ENABLE_DATA_SOURCE=false"}
    try:
        await ds.query("SELECT 1")
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "fail", "error": str(exc)}


async def _check_event_log(event_log: Any) -> dict[str, Any]:
    # MemoryEventLog has no network; treat presence as ok.
    if event_log is None:
        return {"status": "skipped", "reason": "no event_log"}
    return {"status": "ok"}


async def _check_checkpointer(checkpointers: Any) -> dict[str, Any]:
    if checkpointers is None:
        return {"status": "skipped", "reason": "no checkpointer"}
    # setup() already ran in lifespan; memory and PG factories expose no ping —
    # report ok if object exists post-setup.
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request):
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
    body = {"status": "not_ready" if failed else "ready", "checks": checks}
    if failed:
        return JSONResponse(status_code=503, content=body)
    return body
