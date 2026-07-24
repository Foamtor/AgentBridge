"""PrometheusMetrics unit tests."""

from __future__ import annotations

from adapters.prometheus_metrics import PrometheusMetrics


def test_prometheus_render_counter_and_observe() -> None:
    m = PrometheusMetrics()
    m.inc("agentbridge_runs_total", labels={"route": "echo"})
    m.observe("agentbridge_run_seconds", 0.5, labels={"route": "echo"})
    text = m.render_prometheus()
    assert "agentbridge_runs_total" in text
    assert 'route="echo"' in text
    assert "agentbridge_run_seconds_count" in text
