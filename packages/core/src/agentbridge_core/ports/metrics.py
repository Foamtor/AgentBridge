"""Metrics protocol (Prometheus text via host adapter)."""

from __future__ import annotations

from typing import Protocol


class Metrics(Protocol):
    def inc(
        self,
        name: str,
        *,
        labels: dict[str, str] | None = None,
        value: float = 1.0,
    ) -> None: ...

    def observe(
        self,
        name: str,
        value: float,
        *,
        labels: dict[str, str] | None = None,
    ) -> None: ...

    def render_prometheus(self) -> str: ...
