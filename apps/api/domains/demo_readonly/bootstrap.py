"""Register the demo_readonly domain into core registries."""

from __future__ import annotations

from typing import Any

DOMAIN_META = {"description": "只读订单列表示例插件"}

from domains.demo_readonly.graph import build_demo_readonly_graph
from domains.demo_readonly.tools import list_orders


def _build_input(query: str, **kwargs: Any) -> dict[str, Any]:
    return {"messages": [{"role": "user", "content": query}]}


def register(graphs: Any, tools: Any, input_builders: Any | None = None) -> None:
    tools.register("demo_readonly", [list_orders])
    graphs.register("demo_readonly", build_demo_readonly_graph)
    if input_builders is not None:
        input_builders.register("demo_readonly", _build_input)
