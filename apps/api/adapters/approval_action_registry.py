"""Host-side registry for persisted approval action handlers."""

from __future__ import annotations

from typing import Any

from agentbridge_core.protocol.context import RunContext
from agentbridge_core.protocol.fragments import OutboundFragment


class ApprovalActionRegistry:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], tuple[Any, dict[str, Any]]] = {}

    def register(
        self, route: str, action_type: str, handler: Any, resource: dict[str, Any]
    ) -> None:
        key = (route, action_type)
        if key in self._items:
            raise ValueError(f"approval action already registered: {route}/{action_type}")
        self._items[key] = (handler, dict(resource))

    def resource_for(self, *, route: str, action: dict[str, Any]) -> dict[str, Any]:
        _, resource = self._item_for(route, action)
        return dict(resource)

    async def execute(
        self,
        *,
        route: str,
        action: dict[str, Any],
        requester_ctx: RunContext,
        approval_id: str,
    ) -> list[OutboundFragment]:
        handler, _ = self._item_for(route, action)
        fragments = await handler(
            action=action, requester_ctx=requester_ctx, approval_id=approval_id
        )
        if not isinstance(fragments, list) or not all(
            isinstance(item, OutboundFragment) for item in fragments
        ):
            raise ValueError("approval action handler must return OutboundFragment list")
        return fragments

    def _item_for(self, route: str, action: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        action_type = action.get("type") if isinstance(action, dict) else None
        payload = action.get("payload") if isinstance(action, dict) else None
        if not isinstance(action_type, str) or not isinstance(payload, dict):
            raise ValueError("approval action requires type and object payload")
        item = self._items.get((route, action_type))
        if item is None:
            raise ValueError(f"no approval action for route={route} type={action_type}")
        return item
