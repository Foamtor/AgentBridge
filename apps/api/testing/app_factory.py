"""Ensure apps/api is imported instead of a shadowed site-packages ``main``."""

from __future__ import annotations

import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1]


def ensure_api_on_path() -> Path:
    """Put apps/api first on sys.path; drop a wrong ``main`` module if loaded."""
    api = str(_API_ROOT)
    while api in sys.path:
        sys.path.remove(api)
    sys.path.insert(0, api)

    existing = sys.modules.get("main")
    if existing is not None:
        ef = Path(getattr(existing, "__file__", "") or "").resolve()
        if ef != (_API_ROOT / "main.py").resolve():
            del sys.modules["main"]
    return _API_ROOT


def create_test_app():
    """Import create_app only after path fix (safe from repo root)."""
    ensure_api_on_path()
    from main import create_app

    return create_app()
