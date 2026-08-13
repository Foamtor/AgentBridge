from __future__ import annotations

DOMAIN_META = {"description": "先从知识库查找内容再回答，用于验证知识检索流程"}

from agentbridge_core.registry.graphs import GraphRegistry
from agentbridge_core.registry.input_builders import InputBuilderRegistry
from agentbridge_core.registry.tools import ToolRegistry

from domains.demo_rag.graph import build_demo_rag_graph, search_knowledge


def _input_builder(query: str, *, model: str | None = None, extra: dict | None = None):
    return {"messages": [{"role": "user", "content": query}]}


def register(
    graphs: GraphRegistry,
    tools: ToolRegistry,
    input_builders: InputBuilderRegistry,
) -> None:
    tools.register("demo_rag", [search_knowledge])
    graphs.register("demo_rag", build_demo_rag_graph)
    input_builders.register("demo_rag", _input_builder)
