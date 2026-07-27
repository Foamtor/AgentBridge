"""Admin config write API tests."""

from __future__ import annotations


def test_put_config_rejects_tier_b_and_c(client) -> None:
    r = client.put("/admin/config/LLM_BACKEND", json={"value": "gateway"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "config_not_writable"


def test_put_config_tier_a_updates_value(client) -> None:
    r = client.put("/admin/config/RATE_LIMIT_PER_MINUTE", json={"value": 42})
    assert r.status_code == 200
    body = r.json()
    assert body["key"] == "RATE_LIMIT_PER_MINUTE"
    assert body["value"] == 42
    assert body["tier"] == "A"
