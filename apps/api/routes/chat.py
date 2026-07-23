"""POST /chat/stream and /chat/cancel."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from agent_base_core.adapters.sse_event_sink import SseEventSink
from agent_base_core.application.errors import RunNotFound, ThreadBusy, UnknownRoute
from agent_base_core.application.run_lifecycle import RunLifecycle
from agent_base_core.protocol.sse import format_sse_line
from agent_base_core.public import cancel_run, orchestration_stream
from deps import get_run_lifecycle
from routes.schemas import CancelRequest, ChatStreamRequest

router = APIRouter(prefix="/chat", tags=["chat"])


def _http_error(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": message, **extra},
    )


@router.post("/stream")
async def chat_stream(
    body: ChatStreamRequest,
    request: Request,
    lifecycle: RunLifecycle = Depends(get_run_lifecycle),
) -> StreamingResponse:
    graphs = request.app.state.graphs
    try:
        graphs.get(body.route)
    except UnknownRoute as exc:
        raise _http_error(
            400,
            "unknown_route",
            f"unknown route: {body.route}",
            route=body.route,
        ) from exc

    queue: asyncio.Queue[dict[str, Any] | None | tuple[str, BaseException]] = asyncio.Queue()
    sink = SseEventSink(queue)  # type: ignore[arg-type]

    async def _run() -> None:
        try:
            await orchestration_stream(
                lifecycle,
                query=body.query,
                thread_id=body.thread_id,
                route=body.route,
                sink=sink,
                model=body.model,
                extra=body.extra,
            )
        except ThreadBusy as exc:
            await queue.put(("__error__", exc))
            await queue.put(None)
        except UnknownRoute as exc:
            await queue.put(("__error__", exc))
            await queue.put(None)
        except Exception as exc:  # noqa: BLE001 — surface as stream error frame path
            await queue.put(("__error__", exc))
            await queue.put(None)

    task = asyncio.create_task(_run())
    first = await queue.get()
    if isinstance(first, tuple) and first[0] == "__error__":
        err = first[1]
        await task
        if isinstance(err, ThreadBusy):
            raise _http_error(
                409,
                "thread_busy",
                "thread already has a running run",
                thread_id=body.thread_id,
            )
        if isinstance(err, UnknownRoute):
            raise _http_error(
                400,
                "unknown_route",
                f"unknown route: {body.route}",
                route=body.route,
            )
        raise err

    async def event_gen() -> AsyncIterator[str]:
        try:
            if first is not None and not (isinstance(first, tuple) and first[0] == "__error__"):
                yield format_sse_line(first)  # type: ignore[arg-type]
            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, tuple) and item[0] == "__error__":
                    break
                yield format_sse_line(item)  # type: ignore[arg-type]
        finally:
            await task

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/cancel")
async def chat_cancel(
    body: CancelRequest,
    lifecycle: RunLifecycle = Depends(get_run_lifecycle),
) -> dict[str, bool]:
    try:
        await cancel_run(lifecycle, thread_id=body.thread_id, run_id=body.run_id)
    except RunNotFound as exc:
        raise _http_error(
            404,
            "run_not_found",
            "no active run for thread",
            thread_id=body.thread_id,
        ) from exc
    return {"ok": True}
