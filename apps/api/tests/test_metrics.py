"""GET /metrics after a run."""

from __future__ import annotations


def test_metrics_contains_runs_total(client) -> None:
    r = client.post(
        "/chat/stream",
        json={"query": "metrics", "thread_id": "t-metrics-1", "route": "echo"},
    )
    assert r.status_code == 200
    m = client.get("/metrics")
    assert m.status_code == 200
    text = m.text
    assert "agentbridge_runs_total" in text
    assert 'route="echo"' in text
