"""Optional OpenTelemetry run spans (noop until OTEL_ENABLED wiring grows)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def start_run_span(
    run_id: str, route: str, tenant_id: str, *, enabled: bool = False
) -> Iterator[None]:
    """Yield a run span context. No-op today; safe when enabled=True without SDK."""
    _ = (run_id, route, tenant_id, enabled)
    yield


def make_run_span_factory(*, enabled: bool):
    """Return a contextmanager factory suitable for RunLifecycle.span_factory."""

    def _factory(*, run_id: str, route: str, tenant_id: str):
        return start_run_span(run_id, route, tenant_id, enabled=enabled)

    return _factory
