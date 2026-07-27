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
