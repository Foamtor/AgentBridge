import pytest

from agent_base_core.protocol.events import (
    EVENT_TYPES,
    build_event,
    build_extension_event,
)
from agent_base_core.protocol.sse import format_sse_line


def test_build_start_event_shape():
    evt = build_event(
        "start",
        run_id="r1",
        sequence=1,
        trace_id="tr1",
        data={"thread_id": "t1", "route": "echo"},
    )
    assert isinstance(evt, dict)
    assert evt["type"] == "start"
    assert evt["event_id"] == "r1-1"
    assert "timestamp" in evt
    assert evt["data"]["route"] == "echo"


def test_format_sse_line():
    line = format_sse_line({"type": "done", "run_id": "r1"})
    assert line.startswith("data: ")
    assert line.endswith("\n\n")


def test_stable_types_cover_contracts():
    required = {
        "start",
        "step_update",
        "text_delta",
        "tool_call",
        "tool_result",
        "done",
        "error",
        "cancel_requested",
        "cancelled",
    }
    assert required <= EVENT_TYPES


def test_build_event_rejects_extension_type():
    with pytest.raises(ValueError):
        build_event("x.demo.finished", run_id="r1", sequence=1, trace_id="t1")


def test_build_extension_event_ok():
    evt = build_extension_event(
        "x.demo_tools.finished",
        run_id="r1",
        sequence=3,
        trace_id="tr",
        data={"ok": True},
    )
    assert evt["type"] == "x.demo_tools.finished"
    assert evt["event_id"] == "r1-3"
    assert evt["data"]["ok"] is True


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "X.UPPER.x",
        "x.",
        "x.A.b",
        "custom",
        "x.demo",
        "x.123b.c",
        "x..c",
        "x.a.b@d",
    ],
)
def test_build_extension_event_rejects_bad(bad):
    with pytest.raises(ValueError):
        build_extension_event(bad, run_id="r1", sequence=1, trace_id="t1")
