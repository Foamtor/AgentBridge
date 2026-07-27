"""Admin token usage API tests."""

from __future__ import annotations


def test_usage_tokens_group_by_route(client) -> None:
    r = client.get("/admin/usage/tokens?group_by=route")
    assert r.status_code == 200
    body = r.json()
    assert body["group_by"] == "route"
    assert "items" in body


def test_usage_tokens_empty_returns_200_empty_items(client) -> None:
    r = client.get("/admin/usage/tokens?group_by=model")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_usage_tokens_invalid_group_by(client) -> None:
    r = client.get("/admin/usage/tokens?group_by=invalid")
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_group_by"


def test_usage_tokens_respects_time_window(client) -> None:
    store = client.app.state.usage_store
    store.record(
        tenant_id="default",
        route="echo",
        model="gpt-4o",
        input_tokens=10,
        output_tokens=5,
        recorded_at="2020-01-01T00:00:00+00:00",
    )
    store.record(
        tenant_id="default",
        route="echo",
        model="gpt-4o",
        input_tokens=20,
        output_tokens=8,
        recorded_at="2030-01-01T00:00:00+00:00",
    )
    r = client.get(
        "/admin/usage/tokens?group_by=route&since=2029-01-01T00:00:00Z"
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["input_tokens"] == 20
    assert body["items"][0]["model"] == "gpt-4o"
