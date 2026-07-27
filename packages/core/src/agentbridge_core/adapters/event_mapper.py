"""Map runtime signals to OutboundFragment (no envelope numbering)."""

from __future__ import annotations

from typing import Any

from agentbridge_core.protocol.fragments import OutboundFragment


def map_text_delta(content: str) -> OutboundFragment:
    return OutboundFragment(type="text_delta", data={"content": content})


def map_tool_call(
    name: str,
    args: dict[str, Any],
    tool_call_id: str,
) -> OutboundFragment:
    return OutboundFragment(
        type="tool_call",
        data={"name": name, "args": args, "tool_call_id": tool_call_id},
    )


def map_tool_result(
    name: str, *, ok: bool, tool_call_id: str, summary: str
) -> OutboundFragment:
    return OutboundFragment(
        type="tool_result",
        data={
            "name": name,
            "ok": ok,
            "tool_call_id": tool_call_id,
            "summary": summary,
        },
    )


def map_step_update(step: str, status: str) -> OutboundFragment:
    return OutboundFragment(type="step_update", step=step, status=status)
