"""GET /ready in memory mode."""

from __future__ import annotations


def test_ready_memory_mode_200(client) -> None:
    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"]["checkpointer"]["status"] == "ok"
    assert body["checks"]["event_log"]["status"] == "ok"
    assert body["checks"]["data_source"]["status"] == "skipped"
