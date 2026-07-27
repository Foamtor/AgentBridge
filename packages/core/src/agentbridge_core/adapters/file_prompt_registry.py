"""File-backed PromptRegistry — ``{name}.md`` / ``{name}.txt`` under a root."""

from __future__ import annotations

from pathlib import Path


class FilePromptRegistry:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def render(self, name: str, /, **vars: str) -> str:
        for ext in (".md", ".txt"):
            path = self._root / f"{name}{ext}"
            if path.is_file():
                return path.read_text(encoding="utf-8").format(**vars)
        raise FileNotFoundError(f"prompt not found: {name}")
