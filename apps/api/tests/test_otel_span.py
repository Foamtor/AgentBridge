"""OTel span factory does not raise."""

from __future__ import annotations

from observability.tracing import make_run_span_factory, start_run_span


def test_start_run_span_noop() -> None:
    with start_run_span("r1", "echo", "t1", enabled=False):
        pass
    with start_run_span("r1", "echo", "t1", enabled=True):
        pass


def test_span_factory_usable(client) -> None:
    # Smoke: app boots with span_factory; a stream succeeds.
    r = client.post(
        "/chat/stream",
        json={"query": "otel", "thread_id": "t-otel", "route": "echo"},
    )
    assert r.status_code == 200
    factory = make_run_span_factory(enabled=True)
    with factory(run_id="r", route="echo", tenant_id="t"):
        pass
