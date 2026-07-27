"""Search plugin ``prompts/`` directories for file-backed prompts."""

from __future__ import annotations

from pathlib import Path

from agent_base_core.adapters.file_prompt_registry import FilePromptRegistry


class DomainFilePromptRegistry:
    """Resolve prompts from ``domains/<plugin>/prompts/{name}.md``."""

    def __init__(self, domains_root: str | Path) -> None:
        self._root = Path(domains_root)

    def render(self, name: str, /, **vars: str) -> str:
        for domain in sorted(self._root.iterdir()):
            if not domain.is_dir() or domain.name.startswith("_"):
                continue
            prompts_dir = domain / "prompts"
            if not prompts_dir.is_dir():
                continue
            try:
                return FilePromptRegistry(prompts_dir).render(name, **vars)
            except FileNotFoundError:
                continue
        raise FileNotFoundError(f"prompt not found: {name}")
