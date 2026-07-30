"""Ports for executing persisted approval actions after human approval."""

from __future__ import annotations

from typing import Any, Protocol

from agentbridge_core.protocol.context import RunContext
from agentbridge_core.protocol.fragments import OutboundFragment


class ApprovalResumeExecutor(Protocol):
    def resource_for(self, *, route: str, action: dict[str, Any]) -> dict[str, Any]: ...

    async def execute(
        self,
        *,
        route: str,
        action: dict[str, Any],
        requester_ctx: RunContext,
        approval_id: str,
    ) -> list[OutboundFragment]: ...


class ApprovalActionHandler(Protocol):
    async def __call__(
        self,
        *,
        action: dict[str, Any],
        requester_ctx: RunContext,
        approval_id: str,
    ) -> list[OutboundFragment]: ...


class ApprovalActionRegistrar(Protocol):
    def register(
        self,
        route: str,
        action_type: str,
        handler: ApprovalActionHandler,
        resource: dict[str, Any],
    ) -> None: ...
