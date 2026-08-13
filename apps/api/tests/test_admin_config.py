"""Admin config API tests."""

from __future__ import annotations

from config.settings import Settings
from routes.admin_config import _CONFIG_MANIFEST, project_config


def test_admin_config_masks_secrets(client) -> None:
    r = client.get("/admin/config")
    assert r.status_code == 200
    item = next(x for x in r.json()["items"] if x["key"] == "EMBED_API_KEY")
    assert item["value"] is None
    assert isinstance(item["configured"], bool)
    assert item["tier"] == "C"


def test_config_manifest_covers_settings_fields() -> None:
    settings_fields = set(Settings.model_fields)
    for spec in _CONFIG_MANIFEST:
        assert spec.field in settings_fields, spec.field


def test_project_config_excludes_tier_a_by_default() -> None:
    items = project_config(Settings())
    assert all(item["tier"] != "A" for item in items)
    keys = {item["key"] for item in items}
    assert "LLM_BACKEND" in keys
    assert "LLM_MODE" in keys
    assert "LLM_MODEL" in keys
    assert "EMBED_API_KEY" in keys
    assert "RATE_LIMIT_PER_MINUTE" not in keys


def test_project_config_includes_tier_a_when_requested() -> None:
    items = project_config(Settings(), include_tier_a=True)
    keys = {item["key"] for item in items}
    assert "RATE_LIMIT_PER_MINUTE" in keys
    assert "ADMIN_TOOL_INVOKE_ENABLED" in keys
