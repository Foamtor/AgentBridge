from agent_base_core.protocol.events import EVENT_TYPES, build_event
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
