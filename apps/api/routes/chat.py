"""POST /chat/stream and /chat/cancel."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from agent_base_core.adapters.sse_event_sink import SseEventSink
from agent_base_core.application.errors import RunNotFound, ThreadBusy, UnknownRoute
from agent_base_core.application.pipeline import RequestPipeline
from agent_base_core.application.run_lifecycle import RunLifecycle
from agent_base_core.protocol.sse import format_sse_line
from agent_base_core.public import cancel_run, orchestration_stream
from auth.run_context import claims_to_run_context
from deps import get_pipeline, get_run_lifecycle
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
    pipeline: RequestPipeline = Depends(get_pipeline),
    lifecycle: RunLifecycle = Depends(get_run_lifecycle),
) -> StreamingResponse:
    queue: asyncio.Queue[dict[str, Any] | None | tuple[str, BaseException]] = asyncio.Queue()
    sink = SseEventSink(queue)  # type: ignore[arg-type]
    cancelled_on_disconnect = False
    settings = request.app.state.settings
    claims = getattr(request.state, "auth_claims", None)
    ctx = claims_to_run_context(claims, auth_required=settings.auth_required)

    async def _run() -> None:
        try:
            await orchestration_stream(
                pipeline,
                query=body.query,
                thread_id=body.thread_id,
                route=body.route,
                sink=sink,
                model=body.model,
                extra=body.extra,
                ctx=ctx,
            )
        except ThreadBusy as exc:
            await queue.put(("__error__", exc))
            await queue.put(None)
        except UnknownRoute as exc:
            await queue.put(("__error__", exc))
            await queue.put(None)
        except Exception as exc:  # noqa: BLE001
            # Pre-start failures re-raise from lifecycle (no SSE yet). Mid-stream
            # failures are emitted as error by lifecycle and do not re-raise.
            await queue.put(("__error__", exc))
            await queue.put(None)

    task = asyncio.create_task(_run())
    first = await queue.get()
    if first is None:
        await task
        raise _http_error(
            500,
            "stream_failed",
            "stream ended before any event",
            thread_id=body.thread_id,
        )
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
        raise _http_error(
            500,
            "stream_failed",
            str(err),
            thread_id=body.thread_id,
        )

    async def event_gen() -> AsyncIterator[str]:
        nonlocal cancelled_on_disconnect
        try:
            if first is not None and not (
                isinstance(first, tuple) and first[0] == "__error__"
            ):
                yield format_sse_line(first)  # type: ignore[arg-type]
            while True:
                if await request.is_disconnected():
                    if not cancelled_on_disconnect:
                        cancelled_on_disconnect = True
                        try:
                            await cancel_run(lifecycle, thread_id=body.thread_id)
                        except RunNotFound:
                            pass
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    continue
                if item is None:
                    break
                if isinstance(item, tuple) and item[0] == "__error__":
                    # Mid-stream host errors must not synthesize r-host frames;
                    # lifecycle owns terminal error events.
                    break
                yield format_sse_line(item)  # type: ignore[arg-type]
        finally:
            if not task.done() and not cancelled_on_disconnect:
                try:
                    await cancel_run(lifecycle, thread_id=body.thread_id)
                except RunNotFound:
                    pass
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
