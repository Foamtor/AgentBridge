"""Runtime that requests HIL approval then stops (tests / demo)."""

from __future__ import annotations

from typing import Any

from agent_base_core.protocol.fragments import OutboundFragment


class ApprovalAwareRuntime:
    """Yields ``x.bridge.approval_required`` then ends (lifecycle pauses)."""

    def __init__(self, *, timeout_seconds: float = 30.0, tool: str = "write_record") -> None:
        self.timeout_seconds = timeout_seconds
        self.tool = tool

    async def astream(self, builder: Any, **kwargs: Any):
        _ = (builder, kwargs)
        yield OutboundFragment(
            type="x.bridge.approval_required",
            data={
                "tool": self.tool,
                "timeout_seconds": self.timeout_seconds,
            },
        )
