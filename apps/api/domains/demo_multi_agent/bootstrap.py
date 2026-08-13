from __future__ import annotations

DOMAIN_META = {"description": "让多个角色分工处理同一问题，用于验证协作流程"}

from agentbridge_core.registry.graphs import GraphRegistry
from agentbridge_core.registry.input_builders import InputBuilderRegistry
from agentbridge_core.registry.tools import ToolRegistry

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
