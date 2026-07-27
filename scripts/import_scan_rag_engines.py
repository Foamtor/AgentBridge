"""Fail if domains or core application import knowledge engine SDKs."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

FORBIDDEN_PREFIXES = (
    "langchain_postgres",
    "langchain_openai",
    "langchain_community",
)
ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (
    ROOT / "apps" / "api" / "domains",
    ROOT / "packages" / "core" / "src" / "agent_base_core" / "application",
)


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append((node.lineno, node.module))
    return found


def main() -> int:
    violations: list[str] = []
    for base in SCAN_ROOTS:
        if not base.is_dir():
            print(f"scan root missing: {base}", file=sys.stderr)
            return 1
        for py in base.rglob("*.py"):
            rel = py.relative_to(ROOT)
            for lineno, mod in _imports(py):
                for bad in FORBIDDEN_PREFIXES:
                    if mod == bad or mod.startswith(f"{bad}."):
                        violations.append(f"{rel}:{lineno} imports {mod!r}")
    if violations:
        print("Forbidden engine imports:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print("import_scan_rag_engines: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
