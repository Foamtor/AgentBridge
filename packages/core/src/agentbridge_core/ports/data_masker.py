"""DataMasker protocol — reversible PII tokens bound to a run."""

from __future__ import annotations

from typing import Protocol


class DataMasker(Protocol):
    def mask(self, text: str, token_map: dict[str, str]) -> str: ...

    def unmask(self, text: str, token_map: dict[str, str]) -> str: ...
