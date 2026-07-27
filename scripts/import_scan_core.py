"""Fail if packages/core src leaks domain names or product packages."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

FORBIDDEN_IMPORTS = ("ai_map_chat", "app_ai_chat", "knowlede")
# Domain / node names must not appear in core *source* (tests may use x.demo_tools.*).
FORBIDDEN_SUBSTRINGS = ("demo_tools", "echo_node")
CORE_ROOT = Path(__file__).resolve().parents[1] / "packages" / "core"
CORE_SRC = CORE_ROOT / "src" / "agentbridge_core"


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
        text = py.read_text(encoding="utf-8")
        rel = py.relative_to(CORE_ROOT.parent.parent)
        for lineno, mod in _imports_in_file(py):
            for bad in FORBIDDEN_IMPORTS:
                if mod == bad or mod.startswith(f"{bad}."):
                    violations.append(f"{rel}:{lineno} imports forbidden module {mod!r}")
        for bad in FORBIDDEN_SUBSTRINGS:
            if bad in text:
                violations.append(f"{rel} contains forbidden token {bad!r}")

    if violations:
        print("Forbidden content in packages/core/src:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print("import_scan_core: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
