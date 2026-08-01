"""guard_tools wraps invoke with policy + audit."""

from __future__ import annotations

from typing import Annotated

import pytest

from agentbridge_core.adapters.memory_audit_logger import MemoryAuditLogger
from agentbridge_core.adapters.role_policy import RolePolicyEngine
from agentbridge_core.application.tool_guard import guard_tools
from agentbridge_core.protocol.context import RUN_CONTEXT_KEY, RunContext, get_run_context
from agentbridge_core.protocol.tool_meta import attach_tool_meta
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool


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


@tool
async def _echo_tenant(config: Annotated[RunnableConfig, InjectedToolArg]) -> str:
    """Return tenant_id from injected RunContext (guard regression)."""
    return get_run_context(config).tenant_id


_echo_tenant = attach_tool_meta(_echo_tenant, required_roles=["admin"])


@pytest.mark.asyncio
async def test_guard_denies_invoke_for_viewer() -> None:
    raw = attach_tool_meta(_T(), required_roles=["admin"])
    ctx = RunContext(roles=["viewer"], tenant_id="t", user_id="u1")
    audit = MemoryAuditLogger()
    guarded = guard_tools([raw], policy=RolePolicyEngine(), ctx=ctx, audit=audit)
    result = await guarded[0].ainvoke({})
    assert result == "forbidden"
    assert raw.called is False
    denied = [r for r in audit.records if r["result"] == "denied"]
    assert denied
    assert denied[0]["detail"]["reason_code"] == "role_mismatch"
    assert denied[0]["detail"]["policy_version"] == "role_policy/v1"


@pytest.mark.asyncio
@pytest.mark.parametrize("permissions", [["perm:create"], ["perm:assign"]])
async def test_guard_denies_when_one_all_required_permission_is_missing(
    permissions: list[str],
) -> None:
    raw = attach_tool_meta(
        _T(),
        required_permissions_all=["perm:create", "perm:assign"],
    )
    ctx = RunContext(permissions=permissions, tenant_id="t", user_id="u1")
    audit = MemoryAuditLogger()
    guarded = guard_tools([raw], policy=RolePolicyEngine(), ctx=ctx, audit=audit)

    assert await guarded[0].ainvoke({}) == "forbidden"
    assert raw.called is False
    denied = [record for record in audit.records if record["result"] == "denied"]
    assert denied[0]["detail"]["reason_code"] == "permission_mismatch"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "permissions", [["perm:create", "perm:assign"], ["*"]]
)
async def test_guard_allows_when_all_required_permissions_are_present(
    permissions: list[str],
) -> None:
    raw = attach_tool_meta(
        _T(),
        required_permissions_all=["perm:create", "perm:assign"],
    )
    ctx = RunContext(permissions=permissions, tenant_id="t", user_id="u1")
    guarded = guard_tools([raw], policy=RolePolicyEngine(), ctx=ctx)

    assert await guarded[0].ainvoke({}) == "did-delete"
    assert raw.called is True


@pytest.mark.asyncio
async def test_guard_deny_uses_ctx_policy_bundle_version() -> None:
    raw = attach_tool_meta(_T(), required_roles=["admin"])
    ctx = RunContext(
        roles=["viewer"],
        tenant_id="t",
        user_id="u1",
        policy_bundle_version="bundle/v9",
    )
    audit = MemoryAuditLogger()
    guarded = guard_tools([raw], policy=RolePolicyEngine(), ctx=ctx, audit=audit)
    await guarded[0].ainvoke({})
    denied = [r for r in audit.records if r["result"] == "denied"]
    assert denied[0]["detail"]["policy_version"] == "bundle/v9"


@pytest.mark.asyncio
async def test_guard_allows_invoke_for_admin() -> None:
    raw = attach_tool_meta(_T(), required_roles=["admin"])
    ctx = RunContext(roles=["admin"], tenant_id="t")
    guarded = guard_tools([raw], policy=RolePolicyEngine(), ctx=ctx)
    result = await guarded[0].ainvoke({})
    assert result == "did-delete"
    assert raw.called is True


def test_guard_sync_invoke_denies_and_audits() -> None:
    raw = attach_tool_meta(_T(), required_roles=["admin"])
    ctx = RunContext(roles=["viewer"], tenant_id="t", user_id="u1")
    audit = MemoryAuditLogger()
    guarded = guard_tools([raw], policy=RolePolicyEngine(), ctx=ctx, audit=audit)
    result = guarded[0].invoke({})
    assert result == "forbidden"
    assert raw.called is False
    denied = [r for r in audit.records if r["result"] == "denied"]
    assert denied
    assert denied[0]["detail"]["reason_code"] == "role_mismatch"
    assert denied[0]["detail"]["policy_version"] == "role_policy/v1"


@pytest.mark.asyncio
async def test_guard_preserves_injected_tool_arg_on_structured_tool() -> None:
    """Wrapping must not strip InjectedToolArg (RunnableConfig) from BaseTool."""
    ctx = RunContext(tenant_id="acme", roles=["admin"])
    guarded = guard_tools([_echo_tenant], policy=RolePolicyEngine(), ctx=ctx)
    config = {"configurable": {RUN_CONTEXT_KEY: ctx}}
    result = await guarded[0].ainvoke({}, config=config)
    assert result == "acme"
