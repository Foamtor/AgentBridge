"""guard_tools wraps invoke with policy + audit."""

from __future__ import annotations

import pytest

from agent_base_core.adapters.memory_audit_logger import MemoryAuditLogger
from agent_base_core.adapters.role_policy import RolePolicyEngine
from agent_base_core.application.tool_guard import guard_tools
from agent_base_core.protocol.context import RunContext
from agent_base_core.registry.tool_meta import attach_tool_meta


class _T:
    name = "delete"

    def __init__(self) -> None:
        self.called = False

    def invoke(self, args):  # noqa: ANN001
        self.called = True
        return "did-delete"

    async def ainvoke(self, args):  # noqa: ANN001
        self.called = True
        return "did-delete"


@pytest.mark.asyncio
async def test_guard_denies_invoke_for_viewer() -> None:
    raw = attach_tool_meta(_T(), required_roles=["admin"])
    ctx = RunContext(roles=["viewer"], tenant_id="t", user_id="u1")
    audit = MemoryAuditLogger()
    guarded = guard_tools([raw], policy=RolePolicyEngine(), ctx=ctx, audit=audit)
    result = await guarded[0].ainvoke({})
    assert result == "forbidden"
    assert raw.called is False
    assert any(r["result"] == "denied" for r in audit.records)


@pytest.mark.asyncio
async def test_guard_allows_invoke_for_admin() -> None:
    raw = attach_tool_meta(_T(), required_roles=["admin"])
    ctx = RunContext(roles=["admin"], tenant_id="t")
    guarded = guard_tools([raw], policy=RolePolicyEngine(), ctx=ctx)
    result = await guarded[0].ainvoke({})
    assert result == "did-delete"
    assert raw.called is True
