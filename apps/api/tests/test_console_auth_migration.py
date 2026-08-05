from pathlib import Path

import pytest

from config.settings import Settings


def test_local_auth_is_the_default(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "local")
    settings = Settings(_env_file=None)
    assert settings.resolved_auth_mode == "local"
    assert settings.auth_password_min_length == 8


def test_settings_accept_auth_mode(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "oidc")
    assert Settings(_env_file=None).auth_mode == "oidc"


def test_local_auth_requires_secure_cookie_in_production(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    with pytest.raises(ValueError, match="AUTH_COOKIE_SECURE"):
        Settings(_env_file=None).validate_auth_mode()

    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    Settings(_env_file=None).validate_auth_mode()


def test_console_auth_migration_contains_no_seed_password():
    sql = Path(__file__).parents[1].joinpath("migrations/009_console_auth.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS console_admins" in sql
    assert "console_sessions" in sql
    assert "console_login_attempts" in sql
    assert "INSERT INTO console_admins" not in sql
    assert "password_hash TEXT NOT NULL" in sql
    assert "initial_password_issued_at TIMESTAMPTZ DEFAULT NOW()" in sql
