"""Optional auth behavior tests."""

from __future__ import annotations

import os

import pytest
from auth.oidc import AuthConfigError, validate_auth_settings
from fastapi.testclient import TestClient
from jose import jwt
from p2a_auth_helpers import bearer_headers


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
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    os.environ["AUTH_REQUIRED"] = "false"
    from testing.app_factory import create_test_app as create_app

    app = create_app()
    with TestClient(app) as c:
        r = c.post(
            "/chat/stream",
            json={"query": "hi", "thread_id": "t-auth-off", "route": "echo"},
        )
    assert r.status_code == 200


def test_auth_on_rejects_missing_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_DEV_STUB", "true")
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["AUTH_DEV_STUB"] = "true"
    from testing.app_factory import create_test_app as create_app

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
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["AUTH_DEV_STUB"] = "false"
    os.environ["OIDC_JWT_SECRET"] = secret
    from testing.app_factory import create_test_app as create_app

    app = create_app()
    with TestClient(app) as c:
        bad = c.post(
            "/chat/stream",
            headers={"Authorization": "Bearer not-a-jwt"},
            json={"query": "hi", "thread_id": "t-bad", "route": "echo"},
        )
        assert bad.status_code == 401
        token = jwt.encode(
            {"sub": "u1", "tenant_id": "acme"}, secret, algorithm="HS256"
        )
        ok = c.post(
            "/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "hi", "thread_id": "t-good", "route": "echo"},
        )
        assert ok.status_code == 200


@pytest.mark.parametrize(
    "claims",
    [
        {"sub": ""},
        {"sub": None},
        {"tenant_id": ""},
        {"tenant_id": None},
        {"tid": "", "tenant_id": None},
    ],
)
def test_auth_required_rejects_missing_identity_claims(
    monkeypatch: pytest.MonkeyPatch,
    claims: dict[str, object],
) -> None:
    secret = "p2a-identity-claims-secret"
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_DEV_STUB", "false")
    monkeypatch.setenv("OIDC_JWT_SECRET", secret)
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    from testing.app_factory import create_test_app

    app = create_test_app()
    with TestClient(app) as client:
        response = client.post(
            "/chat/stream",
            headers=bearer_headers(secret, **claims),
            json={"query": "hi", "thread_id": "p2a-identity", "route": "echo"},
        )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"


def test_invalid_identity_token_creates_no_run_event_or_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "p2a-zero-side-effect-secret"
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_DEV_STUB", "false")
    monkeypatch.setenv("OIDC_JWT_SECRET", secret)
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    from testing.app_factory import create_test_app

    app = create_test_app()
    with TestClient(app) as client:
        response = client.post(
            "/chat/stream",
            headers=bearer_headers(secret, tenant_id=""),
            json={"query": "hi", "thread_id": "p2a-no-side-effect", "route": "echo"},
        )

    assert response.status_code == 401
    assert app.state.run_store._runs == {}
    assert app.state.event_log._by_run == {}
    assert app.state.approval_store._by_id == {}
