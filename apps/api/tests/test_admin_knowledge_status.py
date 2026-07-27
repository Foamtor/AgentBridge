"""Admin knowledge status API tests."""

from __future__ import annotations


def test_admin_knowledge_status_fake_backend(client) -> None:
    r = client.get("/admin/knowledge/status")
    assert r.status_code == 200
    body = r.json()
    assert body["backend"] == "fake"
    assert body["healthy"] is True
    assert body["embedding"]["status"] == "skipped"
    assert isinstance(body["ingest_jobs"], list)


def test_admin_knowledge_status_blocked_without_provider(client) -> None:
    client.app.state.knowledge_status_provider = None
    r = client.get("/admin/knowledge/status")
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "blocked_by_base_r_b_status_api"
