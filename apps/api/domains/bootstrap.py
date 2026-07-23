"""register_all(graphs, tools, input_builders) — call each domain bootstrap."""

from __future__ import annotations

from typing import Any

from domains.echo import bootstrap as echo


def register_all(
    graphs: Any,
    tools: Any,
    input_builders: Any | None = None,
) -> None:
    echo.register(graphs, tools, input_builders)
