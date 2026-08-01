"""P2-A release-validation evidence contract tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "check_p2a_evidence.py"
_EVIDENCE = _ROOT / "docs" / "release-validation" / "p2a-runtime-security-rag-console.md"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_p2a_evidence", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_p2a_evidence_template_is_complete_and_secret_free() -> None:
    module = _load_module()
    errors = module.validate_evidence(_EVIDENCE.read_text(encoding="utf-8"))
    assert errors == []


def test_p2a_evidence_validation_does_not_echo_secret_values() -> None:
    module = _load_module()
    secret = "postgresql://user:do-not-print@db/private"
    errors = module.validate_evidence(f"# P2-A\n{secret}")
    assert errors
    assert all(secret not in error for error in errors)
