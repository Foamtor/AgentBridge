"""ContextManager — trim message history to a token budget."""

from __future__ import annotations

from typing import Any, Protocol


class ContextManager(Protocol):
    def build_messages(
        self, messages: list[Any], *, budget_tokens: int
    ) -> list[Any]: ...
