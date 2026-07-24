"""demo_tools domain tools (no LLM)."""

from __future__ import annotations

from langchain_core.tools import tool


@tool
def add(a: int, b: int) -> int:
    """Return a + b."""
    return a + b
