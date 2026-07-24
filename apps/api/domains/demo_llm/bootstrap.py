"""Register demo_llm domain."""

from __future__ import annotations

from agent_base_core.registry.graphs import GraphRegistry
from agent_base_core.registry.input_builders import InputBuilderRegistry
from agent_base_core.registry.tools import ToolRegistry

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
