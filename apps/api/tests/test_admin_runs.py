"""Admin runs list API tests."""

from __future__ import annotations


def test_admin_runs_filters_by_status_and_route(client) -> None:
    client.post(
        "/chat/stream",
        json={"query": "hello", "thread_id": "t-runs-1", "route": "echo"},
    )
    r = client.get("/admin/runs?status=done&route=echo&limit=20")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert all(item["route"] == "echo" for item in body["items"])
    assert all(item["status"] == "done" for item in body["items"])


def test_admin_runs_empty_when_no_match(client) -> None:
    r = client.get("/admin/runs?status=error&route=missing-route-xyz")
    assert r.status_code == 200
    assert r.json()["items"] == []
