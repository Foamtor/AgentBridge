from types import SimpleNamespace

import pytest
from agent_base_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agent_base_core.adapters.inprocess_lock import InProcessThreadLock
from agent_base_core.adapters.memory_audit_logger import MemoryAuditLogger
from agent_base_core.adapters.noop_hooks import NoopHooks
from agent_base_core.adapters.role_policy import RolePolicyEngine
from agent_base_core.application.pipeline import RequestPipeline, ToolPolicyPlugin
from agent_base_core.application.run_lifecycle import RunLifecycle
from agent_base_core.protocol.context import RunContext
from agent_base_core.registry.input_builders import InputBuilderRegistry
from agent_base_core.registry.tool_meta import attach_tool_meta

from fakes import FakeCheckpointerFactory, FakeRuntime


class CapturingRuntime(FakeRuntime):
    def __init__(self) -> None:
        self.last_tools = None

    async def astream(self, builder, **kwargs):
        self.last_tools = kwargs.get("tools")
        async for frag in super().astream(builder, **kwargs):
            yield frag


@pytest.mark.asyncio
async def test_pipeline_filters_tools(graphs, tools, queue_and_sink, drain_events):
    admin_tool = attach_tool_meta(
        SimpleNamespace(name="delete"), required_roles=["admin"]
    )
    tools.register("echo", [admin_tool])
    runtime = CapturingRuntime()
    lc = RunLifecycle(
        locks=InProcessThreadLock(),
        checkpointers=FakeCheckpointerFactory(),
        graphs=graphs,
        tools=tools,
        input_builders=InputBuilderRegistry(),
        runtime=runtime,
        cancels=InProcessCancelRegistry(),
        hooks=NoopHooks(),
    )
    audit = MemoryAuditLogger()
    pipeline = RequestPipeline(
        lifecycle=lc,
        plugins=[
            ToolPolicyPlugin(
                policy=RolePolicyEngine(),
                audit=audit,
                tools_registry=tools,
            )
        ],
    )
    q, sink = queue_and_sink
    await pipeline.handle(
        query="hi",
        thread_id="t1",
        route="echo",
        sink=sink,
        ctx=RunContext(user_id="v", tenant_id="t", roles=["viewer"]),
    )
    await drain_events(q)
    assert runtime.last_tools == []
    assert any(r["action"] == "list_tools" for r in audit.records)
