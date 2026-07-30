from __future__ import annotations

import pytest


async def handler(**kwargs):  # noqa: ANN003
    return []


def test_registry_rejects_action_registered_for_another_route() -> None:
    from adapters.approval_action_registry import ApprovalActionRegistry

    registry = ApprovalActionRegistry()
    registry.register("route_a", "a.write_v1", handler, {"name": "write"})
    with pytest.raises(ValueError, match="no approval action"):
        registry.resource_for(
            route="route_b", action={"type": "a.write_v1", "payload": {}}
        )
