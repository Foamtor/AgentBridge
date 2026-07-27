"""SafetyHooks outbound redact tests."""

from __future__ import annotations

from agentbridge_core.adapters.safety_hooks import SafetyHooks


def test_safety_hooks_redacts_phone() -> None:
    h = SafetyHooks(redact=True)
    out = h.on_emit_text("reach me at 13900001111")
    assert "13900001111" not in out
    assert "[REDACTED]" in out
    assert h.alerts


def test_safety_hooks_warn_only() -> None:
    h = SafetyHooks(redact=False)
    raw = "13900001111"
    assert h.on_emit_text(raw) == raw
    assert h.alerts
