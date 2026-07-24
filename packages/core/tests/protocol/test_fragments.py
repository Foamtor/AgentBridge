from agent_base_core.protocol.fragments import (
    OUTBOUND_EXTENSIONS_KEY,
    OutboundFragment,
)


def test_outbound_extensions_key_constant():
    assert OUTBOUND_EXTENSIONS_KEY == "outbound_extensions"


def test_outbound_fragment_defaults():
    frag = OutboundFragment(type="text_delta", data={"content": "hi"})
    assert frag.type == "text_delta"
    assert frag.data == {"content": "hi"}
    assert frag.step is None
    assert frag.status is None


def test_outbound_fragment_forbids_envelope_keys_via_extra():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        OutboundFragment.model_validate(
            {"type": "text_delta", "data": {}, "sequence": 1}
        )
