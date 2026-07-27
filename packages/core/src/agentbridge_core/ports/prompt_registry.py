"""PromptRegistry protocol."""

from __future__ import annotations

from typing import Protocol


class PromptRegistry(Protocol):
    def render(self, name: str, /, **vars: str) -> str: ...
