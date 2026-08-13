"""Register demo_llm domain."""

from __future__ import annotations

DOMAIN_META = {"description": "把问题发送给所选模型，用于验证模型连接和回复"}

from agentbridge_core.registry.graphs import GraphRegistry
from agentbridge_core.registry.input_builders import InputBuilderRegistry
from agentbridge_core.registry.tools import ToolRegistry

from domains.demo_llm.graph import ask_model, build_demo_llm_graph


def _input_builder(query: str, *, model: str | None = None, extra: dict | None = None):
    return {"messages": [{"role": "user", "content": query}]}


def register(
    graphs: GraphRegistry,
    tools: ToolRegistry,
    input_builders: InputBuilderRegistry,
) -> None:
    tools.register("demo_llm", [ask_model])
    graphs.register("demo_llm", build_demo_llm_graph)
    input_builders.register("demo_llm", _input_builder)
