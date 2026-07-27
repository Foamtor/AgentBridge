"""No-op Metrics."""

from __future__ import annotations


class NoopMetrics:
    def inc(
        self,
        name: str,
        *,
        labels: dict[str, str] | None = None,
        value: float = 1.0,
    ) -> None:
        return None

    def observe(
        self,
        name: str,
        value: float,
        *,
        labels: dict[str, str] | None = None,
    ) -> None:
        return None

    def render_prometheus(self) -> str:
        return ""
