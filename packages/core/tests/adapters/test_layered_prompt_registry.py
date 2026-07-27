"""LayeredPromptRegistry platform-over-file precedence."""

from __future__ import annotations

from pathlib import Path

from agent_base_core.adapters.file_prompt_registry import FilePromptRegistry
from agent_base_core.adapters.layered_prompt_registry import LayeredPromptRegistry
from agent_base_core.adapters.memory_prompt_registry import MemoryPromptRegistry


def test_layered_prompt_prefers_published_platform(tmp_path: Path) -> None:
    (tmp_path / "greet.md").write_text("file Hello {name}!", encoding="utf-8")
    platform = MemoryPromptRegistry()
    platform.put("greet", content="platform Hello {name}!")
    platform.publish("greet")
    reg = LayeredPromptRegistry(platform, FilePromptRegistry(tmp_path))
    assert reg.render("greet", name="Ada") == "platform Hello Ada!"


def test_layered_prompt_falls_back_to_file(tmp_path: Path) -> None:
    (tmp_path / "greet.md").write_text("file Hello {name}!", encoding="utf-8")
    platform = MemoryPromptRegistry()
    platform.put("greet", content="draft only {name}")
    reg = LayeredPromptRegistry(platform, FilePromptRegistry(tmp_path))
    assert reg.render("greet", name="Ada") == "file Hello Ada!"
