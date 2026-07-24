from __future__ import annotations

from agent_base_core.registry.graphs import GraphRegistry
from agent_base_core.registry.input_builders import InputBuilderRegistry
from agent_base_core.registry.tools import ToolRegistry

from domains.demo_multi_agent.graph import build_demo_multi_agent_graph


def _input_builder(query: str, *, model: str | None = None, extra: dict | None = None):
    return {"messages": [{"role": "user", "content": query}]}


def register(
    graphs: GraphRegistry,
    tools: ToolRegistry,
    input_builders: InputBuilderRegistry,
) -> None:
    tools.register("demo_multi_agent", [])
    graphs.register("demo_multi_agent", build_demo_multi_agent_graph)
    input_builders.register("demo_multi_agent", _input_builder)
