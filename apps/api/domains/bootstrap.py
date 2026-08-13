"""register_all(graphs, tools, input_builders) — call each domain bootstrap."""

from __future__ import annotations

from typing import Any

from domains.demo_approval_write import bootstrap as demo_approval_write
from domains.demo_llm import bootstrap as demo_llm
from domains.demo_multi_agent import bootstrap as demo_multi_agent
from domains.demo_rag import bootstrap as demo_rag
from domains.demo_readonly import bootstrap as demo_readonly
from domains.demo_tools import bootstrap as demo_tools
from domains.echo import bootstrap as echo
from domains.work_order_ops import bootstrap as work_order_ops

DOMAIN_META_MAP: dict[str, dict[str, Any]] = {
    "echo": echo.DOMAIN_META,
    "demo_tools": demo_tools.DOMAIN_META,
    "demo_readonly": demo_readonly.DOMAIN_META,
    "demo_llm": demo_llm.DOMAIN_META,
    "demo_rag": demo_rag.DOMAIN_META,
    "demo_approval_write": demo_approval_write.DOMAIN_META,
    "demo_multi_agent": demo_multi_agent.DOMAIN_META,
    "work_order_ops": work_order_ops.DOMAIN_META,
}


def register_all(
    graphs: Any,
    tools: Any,
    input_builders: Any | None = None,
    **kwargs: Any,
) -> None:
    echo.register(graphs, tools, input_builders)
    demo_tools.register(graphs, tools, input_builders)
    demo_readonly.register(graphs, tools, input_builders)
    demo_llm.register(graphs, tools, input_builders)
    demo_rag.register(graphs, tools, input_builders)
    demo_approval_write.register(graphs, tools, input_builders)
    demo_multi_agent.register(graphs, tools, input_builders)
    work_order_ops.register(graphs, tools, input_builders, **kwargs)
