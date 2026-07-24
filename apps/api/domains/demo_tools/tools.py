"""demo_tools domain tools (no LLM)."""

from __future__ import annotations

from agent_base_core.registry.tool_meta import attach_tool_meta
from langchain_core.tools import tool


@tool
def add(a: int, b: int) -> int:
    """Return a + b."""
    return a + b


@tool
def delete_records(table: str) -> str:
    """Delete records from a table (admin-only demo tool; not used by the graph)."""
    return f"deleted:{table}"


attach_tool_meta(delete_records, required_roles=["admin"])
