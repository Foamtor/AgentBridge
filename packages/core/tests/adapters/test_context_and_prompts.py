"""ContextManager + FilePromptRegistry tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from agent_base_core.adapters.file_prompt_registry import FilePromptRegistry
from agent_base_core.adapters.token_budget_context_manager import (
    TokenBudgetContextManager,
)


def test_build_messages_trims_oldest_under_budget() -> None:
    cm = TokenBudgetContextManager(chars_per_token=1.0)
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "aaaa"},
        {"role": "assistant", "content": "bbbb"},
        {"role": "user", "content": "cccc"},
    ]
    # budget fits system + newest user only (approx by char count)
    out = cm.build_messages(messages, budget_tokens=8)
    roles = [m["role"] for m in out]
    assert "system" in roles
    assert out[-1]["content"] == "cccc"
    assert "aaaa" not in [m["content"] for m in out]


def test_file_prompt_render(tmp_path: Path) -> None:
    (tmp_path / "greet.txt").write_text("Hello {name}!", encoding="utf-8")
    reg = FilePromptRegistry(tmp_path)
    assert reg.render("greet", name="Ada") == "Hello Ada!"


def test_file_prompt_missing(tmp_path: Path) -> None:
    reg = FilePromptRegistry(tmp_path)
    with pytest.raises(FileNotFoundError):
        reg.render("nope")
