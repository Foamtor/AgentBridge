from agent_base_core.protocol.context import (
    RUN_CONTEXT_KEY,
    RunContext,
    checkpoint_thread_key,
    get_run_context,
)


def test_get_run_context_empty():
    assert get_run_context(None).user_id == ""
    assert get_run_context({}).user_id == ""


def test_get_run_context_from_configurable():
    ctx = RunContext(user_id="u1", tenant_id="t1", roles=["viewer"], run_id="r-1")
    config = {"configurable": {RUN_CONTEXT_KEY: ctx.model_dump()}}
    got = get_run_context(config)
    assert got.user_id == "u1" and got.run_id == "r-1"


def test_checkpoint_thread_key():
    assert checkpoint_thread_key("ten", "th") == "ten::th"
