"""register_all(graphs, tools, input_builders) — call each domain bootstrap."""

from __future__ import annotations

from typing import Any

from domains.demo_approval_write import bootstrap as demo_approval_write
from domains.demo_llm import bootstrap as demo_llm
from domains.demo_rag import bootstrap as demo_rag
from domains.demo_readonly import bootstrap as demo_readonly
from domains.demo_tools import bootstrap as demo_tools
from domains.echo import bootstrap as echo


def register_all(
    graphs: Any,
    tools: Any,
    input_builders: Any | None = None,
) -> None:
    echo.register(graphs, tools, input_builders)
    demo_tools.register(graphs, tools, input_builders)
    demo_readonly.register(graphs, tools, input_builders)
    demo_llm.register(graphs, tools, input_builders)
    demo_rag.register(graphs, tools, input_builders)
    demo_approval_write.register(graphs, tools, input_builders)
