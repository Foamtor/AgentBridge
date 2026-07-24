"""Optional auth behavior tests."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from auth.oidc import AuthConfigError, validate_auth_settings


def test_auth_misconfig_raises():
    with pytest.raises(AuthConfigError):
        validate_auth_settings(
            auth_required=True,
            auth_dev_stub=False,
            oidc_issuer="",
            oidc_jwt_secret="",
        )


def test_auth_off_allows_stream_without_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    monkeypatch.setenv("AUTH_DEV_STUB", "false")
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "1")
    os.environ["AUTH_REQUIRED"] = "false"
    from main import create_app

    app = create_app()
    with TestClient(app) as c:
        c.app.state.graphs.register("echo", lambda **kw: object())
        c.app.state.tools.register("echo", [])
        r = c.post(
            "/chat/stream",
            json={"query": "hi", "thread_id": "t-auth-off", "route": "echo"},
        )
    assert r.status_code == 200


def test_auth_on_rejects_missing_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_DEV_STUB", "true")
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "1")
    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["AUTH_DEV_STUB"] = "true"
    from main import create_app

    app = create_app()
    with TestClient(app) as c:
        r = c.post(
            "/chat/stream",
            json={"query": "hi", "thread_id": "t-auth-on", "route": "echo"},
        )
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "unauthorized"


def test_auth_hs256_rejects_forged_and_accepts_valid(monkeypatch: pytest.MonkeyPatch):
    secret = "unit-test-secret"
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_DEV_STUB", "false")
    monkeypatch.setenv("OIDC_JWT_SECRET", secret)
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "1")
    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["AUTH_DEV_STUB"] = "false"
    os.environ["OIDC_JWT_SECRET"] = secret
    from main import create_app

    app = create_app()
    with TestClient(app) as c:
        c.app.state.graphs.register("echo", lambda **kw: object())
        c.app.state.tools.register("echo", [])
        bad = c.post(
            "/chat/stream",
            headers={"Authorization": "Bearer not-a-jwt"},
            json={"query": "hi", "thread_id": "t-bad", "route": "echo"},
        )
        assert bad.status_code == 401
        token = jwt.encode({"sub": "u1"}, secret, algorithm="HS256")
        ok = c.post(
            "/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "hi", "thread_id": "t-good", "route": "echo"},
        )
        assert ok.status_code == 200
