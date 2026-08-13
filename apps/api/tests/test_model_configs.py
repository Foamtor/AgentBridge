"""Model configuration API: encrypted persistence, safe projection, alias refresh."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient


def _client(
    monkeypatch, *, encryption_key: str = "", auth_mode: str = "disabled"
) -> TestClient:
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    monkeypatch.setenv("AUTH_MODE", auth_mode)
    monkeypatch.setenv("AUTH_REQUIRED", "false")
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


def test_openai_compatible_model_disables_implicit_retries(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setitem(
        sys.modules,
        "langchain_openai",
        SimpleNamespace(ChatOpenAI=FakeChatOpenAI),
    )
    from lifespan import _build_openai_compatible_model

    _build_openai_compatible_model(
        api_key="super-secret-key",
        api_base="https://models.example.test/v1",
        model_name="example-model",
        temperature=0.3,
    )

    assert captured["max_retries"] == 0
    assert captured["timeout"] == 10.0


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
            {
                "alias": "production",
                "model_name": "example-model",
                "kind": "real",
                "last_test_status": None,
                "last_tested_at": None,
                "last_test_capability": None,
            }
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


def test_model_key_setup_writes_env_file_after_reauthentication(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / ".env"
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("MODEL_CONFIG_ENCRYPTION_KEY", "")
    monkeypatch.setenv("MODEL_CONFIG_ENV_FILE", str(env_file))
    with _client(monkeypatch, auth_mode="local") as client:
        service = client.app.state.console_auth_service
        initial = __import__("asyncio").run(service.rotate_initial_password())
        assert client.post("/auth/login", json={"username": "admin", "password": initial}).status_code == 200
        password = "Password2026"
        assert client.post("/auth/change-password", json={"current_password": initial, "new_password": password}).status_code == 200

        missing = client.put("/admin/models/encryption-key", json={})
        assert missing.status_code == 401
        assert missing.json()["detail"]["code"] == "current_password_required"

        response = client.put("/admin/models/encryption-key", json={"current_password": password})
        assert response.status_code == 200
        assert response.json() == {"configured": True, "runtime_ready": True, "restart_required": True}
        saved = env_file.read_text(encoding="utf-8")
        key = saved.partition("=")[2].strip()
        from cryptography.fernet import Fernet

        Fernet(key.encode("ascii"))
        assert key not in response.text
        assert client.app.state.model_config_service.encryption_ready is True
        assert client.post("/admin/models", json=_payload()).status_code == 201


def test_model_key_setup_rejects_invalid_operator_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("MODEL_CONFIG_ENCRYPTION_KEY", "")
    monkeypatch.setenv("MODEL_CONFIG_ENV_FILE", str(tmp_path / ".env"))
    with _client(monkeypatch, auth_mode="local") as client:
        service = client.app.state.console_auth_service
        initial = __import__("asyncio").run(service.rotate_initial_password())
        assert client.post("/auth/login", json={"username": "admin", "password": initial}).status_code == 200
        password = "Password2026"
        assert client.post("/auth/change-password", json={"current_password": initial, "new_password": password}).status_code == 200

        response = client.put("/admin/models/encryption-key", json={
            "current_password": password,
            "encryption_key": "not-a-fernet-key",
        })
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "model_config_encryption_key_invalid"


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


def test_model_alias_allows_readable_name_through_encoded_admin_routes(monkeypatch) -> None:
    alias = "深度求索 V4.1 Flash"
    encoded_alias = quote(alias, safe="")

    class TestModel:
        def bind_tools(self, tools, *, tool_choice=None):
            assert tools[0]["function"]["name"] == "agentbridge_connection_probe"
            assert tool_choice is None
            return self

        async def ainvoke(self, prompt):
            if prompt == "Reply exactly: OK":
                return SimpleNamespace(content="OK")
            return SimpleNamespace(
                tool_calls=[
                    {
                        "name": "agentbridge_connection_probe",
                        "args": {"confirmation": "ready"},
                    }
                ]
            )

    with _client(monkeypatch, encryption_key=_key()) as client:
        created = client.post("/admin/models", json=_payload(alias=alias))
        assert created.status_code == 201
        assert created.json()["alias"] == alias

        updated = client.put(
            f"/admin/models/{encoded_alias}",
            json=_payload(alias=None, api_key="", model_name="deepseek-v4-flash"),
        )
        assert updated.status_code == 200
        assert updated.json()["model_name"] == "deepseek-v4-flash"

        client.app.state.model_config_service._build_model = lambda record, key: TestModel()
        tested = client.post(f"/admin/models/{encoded_alias}/test")
        assert tested.status_code == 200
        assert tested.json()["ok"] is True

        assert client.delete(f"/admin/models/{encoded_alias}").status_code == 204


@pytest.mark.parametrize(
    "alias",
    [
        "default",
        "FAST",
        " leading",
        "trailing ",
        "openai/gpt-4.1",
        r"openai\\gpt-4.1",
        "model?preview",
        "model#preview",
        "model\tname",
        "a" * 65,
    ],
)
def test_model_alias_rejects_reserved_or_unsafe_values(monkeypatch, alias: str) -> None:
    with _client(monkeypatch, encryption_key=_key()) as client:
        response = client.post("/admin/models", json=_payload(alias=alias))
    assert response.status_code == 422


def test_model_connection_test_persists_a_successful_remote_check(monkeypatch) -> None:
    class TestModel:
        def bind_tools(self, tools, *, tool_choice=None):
            assert tool_choice is None
            assert tools == [
                {
                    "type": "function",
                    "function": {
                        "name": "agentbridge_connection_probe",
                        "description": "Confirm that the model can select a tool.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "confirmation": {
                                    "type": "string",
                                    "description": "Return exactly ready.",
                                }
                            },
                            "required": ["confirmation"],
                            "additionalProperties": False,
                        },
                    },
                }
            ]
            return self

        async def ainvoke(self, prompt):
            if prompt == "Reply exactly: OK":
                return SimpleNamespace(content="OK")
            assert prompt == (
                "Use the agentbridge_connection_probe function now. "
                "Set confirmation to ready and provide no other answer."
            )
            return SimpleNamespace(
                tool_calls=[
                    {
                        "name": "agentbridge_connection_probe",
                        "args": {"confirmation": "ready"},
                    }
                ]
            )

    with _client(monkeypatch, encryption_key=_key()) as client:
        assert client.post("/admin/models", json=_payload()).status_code == 201
        client.app.state.model_config_service._build_model = lambda record, key: TestModel()

        response = client.post("/admin/models/production/test")

        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert isinstance(response.json()["latency_ms"], int)
        model = client.get("/admin/models").json()["models"][0]
        assert model["last_test_status"] == "success"
        assert model["last_tested_at"]
        assert model["last_test_capability"] == "tool_calling_v1"


def test_model_connection_test_rejects_model_without_tool_calling(monkeypatch) -> None:
    class PlainChatModel:
        async def ainvoke(self, prompt):
            assert prompt == "Reply exactly: OK"
            return SimpleNamespace(content="OK")

    with _client(monkeypatch, encryption_key=_key()) as client:
        assert client.post("/admin/models", json=_payload()).status_code == 201
        client.app.state.model_config_service._build_model = lambda record, key: PlainChatModel()

        response = client.post("/admin/models/production/test")

        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "model_tool_call_test_failed"
        model = client.get("/admin/models").json()["models"][0]
        assert model["last_test_status"] == "failed"
        assert model["last_test_error"] == "tool_call_binding_unsupported"
        assert model["last_test_capability"] is None


def test_model_connection_test_marks_tool_request_failures(monkeypatch) -> None:
    class ToolRequestFailureModel:
        def bind_tools(self, tools, *, tool_choice=None):
            return self

        async def ainvoke(self, prompt):
            if prompt == "Reply exactly: OK":
                return SimpleNamespace(content="OK")
            raise RuntimeError("provider rejected tool choice")

    with _client(monkeypatch, encryption_key=_key()) as client:
        assert client.post("/admin/models", json=_payload()).status_code == 201
        client.app.state.model_config_service._build_model = lambda record, key: ToolRequestFailureModel()

        response = client.post("/admin/models/production/test")

        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "model_tool_call_test_failed"
        model = client.get("/admin/models").json()["models"][0]
        assert model["last_test_error"] == "tool_call_request_failed"


def test_model_connection_test_records_a_safe_failure(monkeypatch) -> None:
    class FailingModel:
        async def ainvoke(self, prompt):
            raise RuntimeError("api key super-secret-key was rejected")

    with _client(monkeypatch, encryption_key=_key()) as client:
        assert client.post("/admin/models", json=_payload()).status_code == 201
        client.app.state.model_config_service._build_model = lambda record, key: FailingModel()

        response = client.post("/admin/models/production/test")

        assert response.status_code == 502
        assert response.json()["detail"]["code"] == "model_connection_test_failed"
        assert "super-secret-key" not in response.text
        model = client.get("/admin/models").json()["models"][0]
        assert model["last_test_status"] == "failed"
        assert model["last_test_error"] == "connection_failed"


def test_model_connection_test_classifies_provider_http_status_without_exposing_body(monkeypatch) -> None:
    class ProviderFailure(RuntimeError):
        status_code = 401
        response = SimpleNamespace(status_code=401, text="secret api key details")

    class FailingModel:
        async def ainvoke(self, prompt):
            raise ProviderFailure()

    with _client(monkeypatch, encryption_key=_key()) as client:
        assert client.post("/admin/models", json=_payload()).status_code == 201
        client.app.state.model_config_service._build_model = lambda record, key: FailingModel()

        response = client.post("/admin/models/production/test")

        assert response.status_code == 502
        assert response.json()["detail"] == {
            "code": "model_connection_test_failed",
            "reason": "connection_http_401",
        }
        assert "secret api key details" not in response.text
        model = client.get("/admin/models").json()["models"][0]
        assert model["last_test_error"] == "connection_http_401"
