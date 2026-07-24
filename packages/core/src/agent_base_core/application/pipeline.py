"""RequestPipeline: ordered before plugins + lifecycle + after_terminal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from agent_base_core.application.run_lifecycle import RunLifecycle
from agent_base_core.errors import UnknownRoute
from agent_base_core.ports.audit_logger import AuditLogger
from agent_base_core.ports.event_sink import EventSink
from agent_base_core.ports.policy import PolicyEngine
from agent_base_core.protocol.context import RunContext
from agent_base_core.registry.tools import ToolRegistry


@dataclass
class PipelineRequest:
    query: str
    thread_id: str
    route: str
    sink: EventSink
    ctx: RunContext
    model: str | None = None
    extra: dict[str, Any] | None = None
    tools_override: list[Any] | None = None


@dataclass
class RunResult:
    ok: bool = True
    error: str | None = None


class PipelinePlugin(Protocol):
    name: str
    order: int

    async def before_run(self, req: PipelineRequest) -> PipelineRequest: ...

    async def after_terminal(self, req: PipelineRequest, result: RunResult) -> None: ...


class ToolPolicyPlugin:
    name = "tool_policy"
    order = 20

    def __init__(
        self,
        policy: PolicyEngine,
        audit: AuditLogger,
        tools_registry: ToolRegistry,
    ) -> None:
        self._policy = policy
        self._audit = audit
        self._tools = tools_registry

    async def before_run(self, req: PipelineRequest) -> PipelineRequest:
        try:
            tools = self._tools.get(req.route)
        except UnknownRoute:
            tools = []
        if not isinstance(tools, list):
            tools = list(tools) if tools else []
        filtered = self._policy.filter_tools(req.route, tools, req.ctx)
        await self._audit.log(
            user_id=req.ctx.user_id,
            tenant_id=req.ctx.tenant_id,
            action="list_tools",
            resource=req.route,
            detail={"before": len(tools), "after": len(filtered)},
            result="ok",
        )
        req.tools_override = filtered
        return req

    async def after_terminal(self, req: PipelineRequest, result: RunResult) -> None:
        return None


class RequestPipeline:
    def __init__(
        self,
        lifecycle: RunLifecycle,
        plugins: list[Any] | None = None,
    ) -> None:
        self._lifecycle = lifecycle
        self._plugins = sorted(list(plugins or []), key=lambda p: p.order)

    async def handle(
        self,
        *,
        query: str,
        thread_id: str,
        route: str,
        sink: EventSink,
        ctx: RunContext,
        model: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        req = PipelineRequest(
            query=query,
            thread_id=thread_id,
            route=route,
            sink=sink,
            ctx=ctx,
            model=model,
            extra=extra,
        )
        for plugin in self._plugins:
            req = await plugin.before_run(req)
        result = RunResult(ok=True)
        try:
            await self._lifecycle.start_stream(
                query=req.query,
                thread_id=req.thread_id,
                route=req.route,
                sink=req.sink,
                model=req.model,
                extra=req.extra,
                ctx=req.ctx,
                tools_override=req.tools_override,
            )
        except Exception as exc:  # noqa: BLE001
            result = RunResult(ok=False, error=str(exc))
            raise
        finally:
            for plugin in self._plugins:
                await plugin.after_terminal(req, result)
