"""Protocol: GraphRuntime."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from agentbridge_core.protocol.fragments import OutboundFragment


class GraphRuntime(Protocol):
    async def astream(
        self,
        builder: Any,
        *,
        tools: Any,
        checkpointer: Any,
        thread_id: str,
        query: str,
        cancel_token: Any,
        extra: dict[str, Any] | None = None,
    ) -> AsyncIterator[OutboundFragment]: ...
