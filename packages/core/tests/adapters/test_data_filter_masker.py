"""DataFilter deny-default + RegexDataMasker roundtrip."""

from __future__ import annotations

from agent_base_core.adapters.allowlist_data_filter import AllowlistDataFilter
from agent_base_core.adapters.regex_data_masker import RegexDataMasker
from agent_base_core.protocol.context import RunContext


def test_data_filter_no_rules_returns_empty() -> None:
    f = AllowlistDataFilter(rules=[])
    rows = [{"id": 1, "secret": "x"}]
    assert f.apply(rows, RunContext()) == []


def test_data_filter_allowlist_fields() -> None:
    f = AllowlistDataFilter(rules=[{"fields": ["id", "status"]}])
    rows = [{"id": 1, "status": "open", "secret": "x"}]
    assert f.apply(rows, RunContext()) == [{"id": 1, "status": "open"}]


def test_regex_masker_phone_roundtrip() -> None:
    m = RegexDataMasker()
    token_map: dict[str, str] = {}
    masked = m.mask("call 13812345678 now", token_map)
    assert "13812345678" not in masked
    assert "[PHONE_1]" in masked
    assert token_map["[PHONE_1]"] == "13812345678"
    assert m.unmask(masked, token_map) == "call 13812345678 now"


def test_token_map_is_run_scoped_dict_contract() -> None:
    """Hosts keep token_map on RunContext.metadata for DataMasker roundtrips."""
    ctx = RunContext(metadata={"token_map": {}})
    m = RegexDataMasker()
    m.mask("13900001111", ctx.metadata["token_map"])
    assert ctx.metadata["token_map"]
