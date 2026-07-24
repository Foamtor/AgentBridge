"""Outbound SSE event builders aligned with docs/contracts.md."""

from __future__ import annotations

import re
import time
from typing import Any

EVENT_TYPES: frozenset[str] = frozenset(
    {
        "start",
        "step_update",
        "text_delta",
        "tool_call",
        "tool_result",
        "done",
        "error",
        "cancel_requested",
        "cancelled",
    }
)

EXTENSION_TYPE_RE: re.Pattern[str] = re.compile(
    r"^x\.[a-z][a-z0-9_]*\.[a-z0-9_.]+$"
)


def build_event(
    type: str,
    *,
    run_id: str,
    sequence: int,
    trace_id: str,
    data: dict[str, Any] | None = None,
    step: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Build a contracts-aligned outbound event dict (stable types only)."""
    if type not in EVENT_TYPES:
        raise ValueError(f"unknown event type: {type}")
    return _envelope(
        type,
        run_id=run_id,
        sequence=sequence,
        trace_id=trace_id,
        data=data,
        step=step,
        status=status,
    )


def build_extension_event(
    type: str,
    *,
    run_id: str,
    sequence: int,
    trace_id: str,
    data: dict[str, Any] | None = None,
    step: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Build an outbound extension event (legal x.* types only)."""
    if not EXTENSION_TYPE_RE.fullmatch(type):
        raise ValueError(f"invalid extension event type: {type}")
    return _envelope(
        type,
        run_id=run_id,
        sequence=sequence,
        trace_id=trace_id,
        data=data,
        step=step,
        status=status,
    )


def _envelope(
    type: str,
    *,
    run_id: str,
    sequence: int,
    trace_id: str,
    data: dict[str, Any] | None,
    step: str | None,
    status: str | None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "type": type,
        "run_id": run_id,
        "event_id": f"{run_id}-{sequence}",
        "sequence": sequence,
        "trace_id": trace_id,
        "timestamp": int(time.time() * 1000),
        "data": {} if data is None else data,
    }
    if step is not None:
        event["step"] = step
    if status is not None:
        event["status"] = status
    return event
