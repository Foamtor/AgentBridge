"""Fail if packages/core imports product business package names."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

FORBIDDEN = ("ai_map_chat", "app_ai_chat", "knowlede")
CORE_SRC = Path(__file__).resolve().parents[1] / "packages" / "core" / "src" / "agent_base_core"


def _imports_in_file(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.append((node.lineno, node.module))
    return found


def main() -> int:
    if not CORE_SRC.is_dir():
        print(f"core source not found: {CORE_SRC}", file=sys.stderr)
        return 1

    violations: list[str] = []
    for py in CORE_SRC.rglob("*.py"):
        for lineno, mod in _imports_in_file(py):
            for bad in FORBIDDEN:
                if mod == bad or mod.startswith(f"{bad}."):
                    rel = py.relative_to(CORE_SRC.parent.parent.parent)
                    violations.append(f"{rel}:{lineno} imports forbidden module {mod!r}")

    if violations:
        print("Forbidden business imports in packages/core:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print("import_scan_core: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
