"""Prompt API tests."""

from __future__ import annotations


def test_prompt_crud_and_publish(client) -> None:
    put = client.put("/prompts/demo_prompt", json={"content": "hello {name}"})
    assert put.status_code == 200
    get_one = client.get("/prompts/demo_prompt")
    assert get_one.status_code == 200
    assert get_one.json()["content"] == "hello {name}"
    pub = client.post("/prompts/demo_prompt/publish")
    assert pub.status_code == 200
    assert pub.json()["status"] == "published"
