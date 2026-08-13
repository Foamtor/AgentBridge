"""Prompt API tests."""

from __future__ import annotations


def test_production_prompt_registry_is_postgres() -> None:
    from adapters.postgres_prompt_registry import PostgresPromptRegistry
    from config.settings import Settings
    from lifespan import _build_prompt_registry

    settings = Settings(
        _env_file=None,
        AGENTBRIDGE_FAKE_RUNTIME=False,
        RUNTIME_CONFIG_BACKEND="postgres",
        PG_DSN="postgresql://u:p@db/agentbridge",
    )

    assert isinstance(_build_prompt_registry(settings), PostgresPromptRegistry)


def test_prompt_crud_and_publish(client) -> None:
    put = client.put("/prompts/demo_prompt", json={"content": "hello {name}"})
    assert put.status_code == 200
    get_one = client.get("/prompts/demo_prompt")
    assert get_one.status_code == 200
    assert get_one.json()["content"] == "hello {name}"
    pub = client.post("/prompts/demo_prompt/publish")
    assert pub.status_code == 200
    assert pub.json()["status"] == "published"
