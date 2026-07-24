"""Register the demo_tools domain into core registries."""

from __future__ import annotations

from typing import Any

from domains.demo_tools.graph import build_demo_tools_graph
from domains.demo_tools.tools import add, delete_records


def _build_input(query: str, **kwargs: Any) -> dict[str, Any]:
    return {"messages": [{"role": "user", "content": query}]}


def register(graphs: Any, tools: Any, input_builders: Any | None = None) -> None:
    # delete_records is registered for policy matrix / list filtering; graph uses add.
    tools.register("demo_tools", [add, delete_records])
    graphs.register("demo_tools", build_demo_tools_graph)
    if input_builders is not None:
        input_builders.register("demo_tools", _build_input)
