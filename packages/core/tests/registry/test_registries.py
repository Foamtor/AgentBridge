import pytest
from agent_base_core.application.errors import UnknownRoute
from agent_base_core.registry.graphs import GraphRegistry
from agent_base_core.registry.input_builders import InputBuilderRegistry
from agent_base_core.registry.tools import ToolRegistry


def test_graph_registry_get_unknown():
    with pytest.raises(UnknownRoute):
        GraphRegistry().get("missing")


def test_graph_registry_roundtrip():
    reg = GraphRegistry()
    reg.register("echo", lambda **kw: "graph")
    assert reg.get("echo")() == "graph"


def test_tool_and_input_builder_registries():
    tools = ToolRegistry()
    tools.register("echo", [])
    assert tools.get("echo") == []
    ib = InputBuilderRegistry()
    ib.register("echo", lambda q, **kw: {"messages": [q]})
    assert "messages" in ib.get("echo")("hi")
