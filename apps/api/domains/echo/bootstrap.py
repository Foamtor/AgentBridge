"""Register the echo domain into core registries."""

from __future__ import annotations

from typing import Any

DOMAIN_META = {"description": "原样返回你的输入，用于确认对话链路是否正常"}

from domains.echo.graph import build_echo_graph
from domains.echo.tools import echo


def _build_input(query: str, **kwargs: Any) -> dict[str, Any]:
    return {"messages": [query], "query": query, "result": ""}


def register(graphs: Any, tools: Any, input_builders: Any | None = None) -> None:
    tools.register("echo", [echo])
    graphs.register("echo", build_echo_graph)
    if input_builders is not None:
        input_builders.register("echo", _build_input)
