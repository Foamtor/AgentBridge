"""Admin overview API tests."""

from __future__ import annotations


def test_admin_overview_contains_infra_ready_and_runs_24h(client) -> None:
    r = client.get("/admin/overview")
    assert r.status_code == 200
    body = r.json()
    assert "infra_ready" in body
    assert "runs_24h" in body
    assert "total" in body["runs_24h"]
    assert "errors" in body["runs_24h"]
    assert "domains" in body
    assert "registered" in body["domains"]
    assert "llm_backend" in body
    assert "knowledge_backend" in body
    assert "recent_failed_runs" in body


def test_admin_overview_counts_recent_run(client) -> None:
    client.post(
        "/chat/stream",
        json={"query": "hello", "thread_id": "t-overview", "route": "echo"},
    )
    r = client.get("/admin/overview")
    assert r.status_code == 200
    assert r.json()["runs_24h"]["total"] >= 1
