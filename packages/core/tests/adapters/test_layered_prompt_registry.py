"""LayeredPromptRegistry platform-over-file precedence."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentbridge_core.adapters.file_prompt_registry import FilePromptRegistry
from agentbridge_core.adapters.layered_prompt_registry import LayeredPromptRegistry
from agentbridge_core.adapters.memory_prompt_registry import MemoryPromptRegistry


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


@pytest.mark.asyncio
async def test_layered_prompt_reads_published_async_platform_entry(tmp_path: Path) -> None:
    (tmp_path / "greet.md").write_text("file Hello {name}!", encoding="utf-8")

    class AsyncPlatform:
        async def get(self, name: str):
            assert name == "greet"
            return {
                "name": name,
                "content": "platform Hello {name}!",
                "status": "published",
                "version": 4,
            }

    reg = LayeredPromptRegistry(AsyncPlatform(), FilePromptRegistry(tmp_path))

    assert await reg.render_async("greet", name="Ada") == "platform Hello Ada!"
    assert await reg.resolve("greet") == {
        "name": "greet",
        "content": "platform Hello {name}!",
        "source": "platform",
        "version": 4,
    }
