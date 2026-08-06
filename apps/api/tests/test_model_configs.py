"""Model configuration API: encrypted persistence, safe projection, alias refresh."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient


def _client(monkeypatch, *, encryption_key: str = "") -> TestClient:
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    monkeypatch.setenv("MODEL_CONFIG_ENCRYPTION_KEY", encryption_key)
    from testing.app_factory import create_test_app

    return TestClient(create_test_app())


def _key() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode("ascii")


def _payload(**overrides):
    return {
        "alias": "production",
        "api_base": "https://models.example.test/v1",
        "model_name": "example-model",
        "api_key": "super-secret-key",
        "temperature": 0.3,
        "enabled": True,
        **overrides,
    }


def test_model_api_encrypts_key_and_never_returns_it(monkeypatch) -> None:
    with _client(monkeypatch, encryption_key=_key()) as client:
        created = client.post("/admin/models", json=_payload())
        assert created.status_code == 201
        assert "api_key" not in created.json()
        assert created.json()["key_configured"] is True

        stored = client.app.state.model_config_service._store.records["production"]
        assert stored["api_key_ciphertext"] != "super-secret-key"
        assert "super-secret-key" not in stored["api_key_ciphertext"]
        assert client.get("/admin/models").json()["models"][0]["api_base"] == "https://models.example.test/v1"
        assert client.get("/models").json()["models"] == [
            {"alias": "production", "model_name": "example-model", "kind": "real"}
        ]


def test_model_update_blank_key_preserves_ciphertext(monkeypatch) -> None:
    with _client(monkeypatch, encryption_key=_key()) as client:
        assert client.post("/admin/models", json=_payload()).status_code == 201
        store = client.app.state.model_config_service._store
        original = store.records["production"]["api_key_ciphertext"]
        updated = client.put("/admin/models/production", json=_payload(alias=None, api_key="", model_name="changed-model"))
        assert updated.status_code == 200
        assert store.records["production"]["api_key_ciphertext"] == original
        assert updated.json()["model_name"] == "changed-model"


def test_model_write_requires_an_encryption_key(monkeypatch) -> None:
    with _client(monkeypatch) as client:
        response = client.post("/admin/models", json=_payload())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "model_config_encryption_key_required"


def test_model_base_rejects_url_embedded_credentials(monkeypatch) -> None:
    with _client(monkeypatch, encryption_key=_key()) as client:
        response = client.post(
            "/admin/models",
            json=_payload(api_base="https://models.example.test/v1?api_key=secret"),
        )
    assert response.status_code == 422


def test_model_alias_refreshes_gateway(monkeypatch) -> None:
    with _client(monkeypatch, encryption_key=_key()) as client:
        service = client.app.state.model_config_service
        built: list[tuple[str, str]] = []
        service._build_model = lambda record, key: built.append((record["alias"], key)) or SimpleNamespace()
        assert client.post("/admin/models", json=_payload()).status_code == 201
        assert built == [("production", "super-secret-key")]
        assert "production" in client.app.state.llm_gateway.aliases()
        assert service.is_real_alias("production")
        assert client.delete("/admin/models/production").status_code == 204
        assert "production" not in client.app.state.llm_gateway.aliases()
