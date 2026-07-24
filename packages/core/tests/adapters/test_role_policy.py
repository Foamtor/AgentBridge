from types import SimpleNamespace

from agent_base_core.adapters.role_policy import RolePolicyEngine
from agent_base_core.protocol.context import RunContext
from agent_base_core.protocol.tool_meta import attach_tool_meta


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


def test_unknown_action_denied():
    engine = RolePolicyEngine()
    assert engine.decide(ctx=RunContext(permissions=["*"]), action="read_data", resource={}) == "deny"
