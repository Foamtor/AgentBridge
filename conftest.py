"""Repo-root pytest hooks — path hygiene for joint core+api runs."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_API = str(_ROOT / "apps" / "api")
_CORE_TESTS = str(_ROOT / "packages" / "core" / "tests")

for path in (_API, _CORE_TESTS):
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)
