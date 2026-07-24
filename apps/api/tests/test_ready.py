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


def test_ready_fails_when_checkpointer_not_setup(client) -> None:
    class NotSetup:
        def is_setup(self) -> bool:
            return False

    client.app.state.checkpointers = NotSetup()
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "not_ready"
    assert r.json()["checks"]["checkpointer"]["status"] == "fail"
