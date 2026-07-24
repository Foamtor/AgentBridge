"""Register the demo_tools domain into core registries."""

from __future__ import annotations

from typing import Any

from domains.demo_tools.graph import build_demo_tools_graph
from domains.demo_tools.tools import add


def _build_input(query: str, **kwargs: Any) -> dict[str, Any]:
    return {"messages": [{"role": "user", "content": query}]}


def register(graphs: Any, tools: Any, input_builders: Any | None = None) -> None:
    tools.register("demo_tools", [add])
    graphs.register("demo_tools", build_demo_tools_graph)
    if input_builders is not None:
        input_builders.register("demo_tools", _build_input)
