"""GET /metrics Prometheus text."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

router = APIRouter(tags=["ops"])


@router.get("/metrics")
async def metrics(request: Request) -> Response:
    body = request.app.state.metrics.render_prometheus()
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")
