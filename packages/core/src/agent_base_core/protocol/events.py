"""Outbound SSE event builders aligned with docs/contracts.md."""

from __future__ import annotations

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
    """Build a contracts-aligned outbound event dict."""
    if type not in EVENT_TYPES:
        raise ValueError(f"unknown event type: {type}")
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
