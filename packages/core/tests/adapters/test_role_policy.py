from types import SimpleNamespace

import pytest

from agentbridge_core.adapters.role_policy import RolePolicyEngine
from agentbridge_core.protocol.context import RunContext
from agentbridge_core.protocol.tool_meta import attach_tool_meta


def _tool(name: str, **meta):
    t = SimpleNamespace(name=name)
    return attach_tool_meta(t, **meta)


def test_filter_tools_hides_admin_tool_from_viewer():
    engine = RolePolicyEngine()
    tools = [
        _tool("add"),
        _tool("delete", required_roles=["admin"]),
    ]
    ctx = RunContext(roles=["viewer"], permissions=[])
    filtered = engine.filter_tools("demo", tools, ctx)
    assert [t.name for t in filtered] == ["add"]


def test_invoke_denied_without_permission():
    engine = RolePolicyEngine()
    ctx = RunContext(roles=["viewer"])
    d = engine.decide(
        ctx=ctx,
        action="invoke_tool",
        resource={"required_roles": ["admin"], "name": "delete"},
    )
    assert d == "deny"


def test_star_permission_allows():
    engine = RolePolicyEngine()
    ctx = RunContext(permissions=["*"])
    d = engine.decide(
        ctx=ctx,
        action="invoke_tool",
        resource={"required_roles": ["admin"], "name": "delete"},
    )
    assert d == "allow"


def test_policy_requires_all_declared_permissions():
    engine = RolePolicyEngine()
    tool = _tool(
        "write",
        required_permissions_all=["perm:create", "perm:assign"],
    )
    ctx = RunContext(user_id="u", tenant_id="acme", permissions=["perm:create"])

    assert engine.filter_tools("route", [tool], ctx) == []
    assert (
        engine.decide(
            ctx=ctx,
            action="invoke_tool",
            resource={
                "name": "write",
                "required_roles": [],
                "required_permissions": [],
                "required_permissions_all": ["perm:create", "perm:assign"],
            },
        )
        == "deny"
    )


@pytest.mark.parametrize(
    ("permissions", "expected_decision"),
    [
        (["perm:create"], "deny"),
        (["perm:assign"], "deny"),
        (["perm:create", "perm:assign"], "allow"),
        (["*"], "allow"),
    ],
)
def test_policy_all_permissions_filters_and_decides_consistently(
    permissions: list[str], expected_decision: str
) -> None:
    engine = RolePolicyEngine()
    tool = _tool(
        "write",
        required_permissions_all=["perm:create", "perm:assign"],
    )
    ctx = RunContext(permissions=permissions)

    filtered = engine.filter_tools("route", [tool], ctx)
    assert [item.name for item in filtered] == (
        ["write"] if expected_decision == "allow" else []
    )
    assert (
        engine.decide(
            ctx=ctx,
            action="invoke_tool",
            resource={
                "name": "write",
                "required_permissions_all": ["perm:create", "perm:assign"],
            },
        )
        == expected_decision
    )


def test_policy_keeps_legacy_permissions_as_any_of():
    engine = RolePolicyEngine()
    tool = _tool("read", required_permissions=["perm:read", "perm:export"])
    ctx = RunContext(permissions=["perm:export"])

    assert engine.filter_tools("route", [tool], ctx) == [tool]


def test_unknown_action_denied():
    engine = RolePolicyEngine()
    assert engine.decide(ctx=RunContext(permissions=["*"]), action="read_data", resource={}) == "deny"
