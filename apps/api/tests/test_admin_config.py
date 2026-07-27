"""Admin config API tests."""

from __future__ import annotations

from routes.admin_config import _CONFIG_MANIFEST, project_config
from config.settings import Settings


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


def test_project_config_excludes_tier_a() -> None:
    items = project_config(Settings())
    assert all(item["tier"] != "A" for item in items)
    keys = {item["key"] for item in items}
    assert "LLM_BACKEND" in keys
    assert "EMBED_API_KEY" in keys
