from __future__ import annotations

DOMAIN_META = {"description": "写操作审批门禁示例插件"}

from agent_base_core.registry.graphs import GraphRegistry
from agent_base_core.registry.input_builders import InputBuilderRegistry
from agent_base_core.registry.tools import ToolRegistry

from domains.demo_approval_write.graph import build_demo_approval_write_graph


def _input_builder(query: str, *, model: str | None = None, extra: dict | None = None):
    return {"messages": [{"role": "user", "content": query}]}


def register(
    graphs: GraphRegistry,
    tools: ToolRegistry,
    input_builders: InputBuilderRegistry,
) -> None:
    tools.register("demo_approval_write", [])
    graphs.register("demo_approval_write", build_demo_approval_write_graph)
    input_builders.register("demo_approval_write", _input_builder)
