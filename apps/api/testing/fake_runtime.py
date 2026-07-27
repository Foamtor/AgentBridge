"""Deterministic GraphRuntime for API tests (AGENTBRIDGE_FAKE_RUNTIME=1)."""

from __future__ import annotations

from typing import Any

from agentbridge_core.protocol.fragments import OutboundFragment


class ApiFakeRuntime:
    async def astream(self, builder: Any, **kwargs: Any):
        yield OutboundFragment(type="text_delta", data={"content": "ok"})
