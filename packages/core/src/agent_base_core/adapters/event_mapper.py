"""Map runtime fragments to outbound protocol events."""

from __future__ import annotations

from typing import Any

from agent_base_core.protocol.events import build_event


def map_text_delta(
    content: str,
    *,
    run_id: str,
    sequence: int,
    trace_id: str,
) -> dict[str, Any]:
    return build_event(
        "text_delta",
        run_id=run_id,
        sequence=sequence,
        trace_id=trace_id,
        data={"content": content},
    )


def map_tool_call(
    name: str,
    args: dict[str, Any],
    tool_call_id: str,
    *,
    run_id: str,
    sequence: int,
    trace_id: str,
) -> dict[str, Any]:
    return build_event(
        "tool_call",
        run_id=run_id,
        sequence=sequence,
        trace_id=trace_id,
        data={"name": name, "args": args, "tool_call_id": tool_call_id},
    )
