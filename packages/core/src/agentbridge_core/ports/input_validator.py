"""InputValidator protocol."""

from __future__ import annotations

from typing import Protocol


class InputValidator(Protocol):
    def validate_query(self, query: str) -> str: ...
