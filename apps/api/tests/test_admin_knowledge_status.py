"""Admin knowledge status API tests."""

from __future__ import annotations


def test_admin_knowledge_status_blocked_without_provider(client) -> None:
    r = client.get("/admin/knowledge/status")
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "blocked_by_base_r_b_status_api"
