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
    assert all(item["tool_count"] == 0 for item in body["items"])
    assert all(item["error"] is None for item in body["items"])


def test_admin_runs_empty_when_no_match(client) -> None:
    r = client.get("/admin/runs?status=error&route=missing-route-xyz")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_admin_runs_cursor_pages_without_overlap(client) -> None:
    for idx in range(3):
        client.post(
            "/chat/stream",
            json={
                "query": f"hello-{idx}",
                "thread_id": f"t-runs-page-{idx}",
                "route": "echo",
            },
        )
    first = client.get("/admin/runs?status=done&route=echo&limit=2")
    assert first.status_code == 200
    body1 = first.json()
    assert len(body1["items"]) == 2
    assert body1["next_cursor"]

    second = client.get(
        f"/admin/runs?status=done&route=echo&limit=2&cursor={body1['next_cursor']}"
    )
    assert second.status_code == 200
    body2 = second.json()
    ids1 = {item["run_id"] for item in body1["items"]}
    ids2 = {item["run_id"] for item in body2["items"]}
    assert ids1.isdisjoint(ids2)


def test_admin_runs_filters_by_thread_and_trace(client) -> None:
    response = client.post(
        "/chat/stream",
        json={"query": "hello", "thread_id": "t-filtered", "route": "echo"},
    )
    assert response.status_code == 200
    run_id = next(
        __import__("json").loads(line[6:])["run_id"]
        for line in response.text.splitlines()
        if line.startswith("data: ")
    )
    by_thread = client.get("/admin/runs?thread_id=t-filtered")
    by_trace = client.get(f"/admin/runs?trace_id={run_id}")
    assert [item["run_id"] for item in by_thread.json()["items"]] == [run_id]
    assert [item["run_id"] for item in by_trace.json()["items"]] == [run_id]
