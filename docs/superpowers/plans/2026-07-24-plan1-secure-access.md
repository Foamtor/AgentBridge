# Plan 1: 可安全接入（M1 + M2a + M2b）Implementation Plan

> **阅读提示：** 这是历史设计/实施记录。文中若仍有偏内部的说法，请以仓库根目录 README、docs/roadmap.md、docs/add-a-domain.md 的白话为准。\n\n> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.  
> **Rev:** r3 — 对齐 v4.1.1；锁与 graph 共用 `storage_key`；标明对下游 Plan 的 **Produces / 验收条件**。  
> **权威说明**：`docs/00-AgentBridge完整方案.md` **v4.1.1** §4.1–4.5、§10；路线图 Plan1 → v0.2

**Goal:** 交付 v0.2：M1 包装 + M2a（RunContext / list+invoke Policy / 审计 / Pipeline）+ M2b（EventLog append-before-emit / 消息与 Run 投影 / REST / replay）。

**Architecture:** Middleware 出身份 `RunContext`；`RequestPipeline` 插件做 tool list 过滤；`RunLifecycle` 两阶段写入 `run_id`、append-before-emit、经 `configurable` 注入上下文；**ThreadLock 与 checkpointer 使用同一 `storage_key=checkpoint_thread_key(...)`**；tool 执行前再 `decide(invoke_tool)`；终端后投影 Message/Run。

**Tech Stack:** Python 3.12+、FastAPI、Pydantic v2、pytest-asyncio、现有 LangGraph Runtime；EventLog/Message **本 plan 默认 Memory adapter**。

## 依赖与验收条件

| 方向 | 内容 |
|------|------|
| **上游** | 无（基于已有 M0） |
| **硬下游等待本 Plan** | Plan2 至少要 **M2a 验收条件**；Plan3/4/5 要 **Plan1 全量（含 M2b RunStore）** 除非另注 |
| **本 Plan 内顺序** | T1→T2→T3→T4→T5→T6→T7（**M2a 验收条件**）→T8→T9→T10（**M2b 验收条件**）→T11；不可跳过 T6 做 T7 |
| **可提前开工** | Plan2 可在 **M2a 验收条件通过后** 与 M2b（T8–T10）并行 |

## Global Constraints

- `application` → 仅 ports/registry/protocol；adapters 只在 `apps/api/lifespan.py` `new`
- `public.py` 只转发；可接受 `lifecycle` 或带 `.handle` 的 pipeline
- 禁止 `ctx: RunContext = None`；只用 `get_run_context`
- **Policy 双检（v4.1.1 §4.3）**：list 过滤 + invoke 再 decide
- EventLog：全量已提交；append 后于 emit；MessageStore 合并 text_delta
- **`storage_key`**：`checkpoint_thread_key(tenant_id or "default", api_thread_id)`；写入 graph `configurable.thread_id` **且** `locks.try_acquire/release(storage_key, run_id)`（对外 HTTP 仍用裸 `thread_id`）
- 包名不改；commit 英文 conventional

## Produces（下游契约）

| 产物 | 供谁用 |
|------|--------|
| `RunContext` / `get_run_context` / `checkpoint_thread_key` | Plan2–5 |
| `RolePolicyEngine` + `attach_tool_meta` + `guard_tools` | Plan2、Plan4、Plan5 eval |
| `RequestPipeline` + `ToolPolicyPlugin` | Plan2–4 |
| `AuditLogger`（Memory） | Plan3 metrics 可旁路；Plan5 导出 |
| `EventLog` / `MessageStore` / **`RunStore`** | Plan4 HIL（`awaiting_approval`）；Plan5 |
| `app.state.pipeline` + claims→ctx | 全部 API Plan |
| 锁键 = storage_key | Plan5 Redis 不得再套一层 tenant 前缀 |

## Spec ↔ Task 映射

| v4.1 | Task |
|------|------|
| §10 / M1 AI+LICENSE | T1 |
| §4.1 RunContext + 租户键 helper | T2 |
| §4.3 Policy list/invoke + meta | T3 |
| §5 审计 | T4 |
| Pipeline + list 过滤 | T5 |
| invoke 双检 + configurable 注入 + 租户 thread 键 | T6 |
| API claims + 矩阵验收 M2a | T7 |
| §4.2 EventLog append-before-emit | T8 |
| Message/Run 投影 + 租户隔离 | T9 |
| REST + replay M2b | T10 |
| 全量回归 | T11 |

## Already done

- [x] M0 编排/SSE/echo/demo_tools/可选 JWT（`request.state.auth_claims`）
- [x] 文档 v4.1 / roadmap（实现未齐）
- [x] **T1–T11 已实现**（分支 `feat/plan1-secure-access`；审阅后补丁含：AI 脚本恢复、cancel 租户键、claims 安全默认、EventLog 租户维、sync deny 审计）

## File map

| 路径 | 职责 |
|------|------|
| `protocol/context.py` | RunContext、`get_run_context`、`checkpoint_thread_key` |
| `ports/policy.py` / `audit_logger.py` / `event_log.py` / `message_store.py` / `run_store.py` | Ports |
| `registry/tool_meta.py` | 权限元数据 |
| `adapters/role_policy.py` / `noop_*` / `memory_*` | Adapters |
| `application/pipeline.py` | RequestPipeline、ToolPolicyPlugin |
| `application/tool_guard.py` | `guard_tools(tools, policy, ctx)` 包装 invoke |
| `application/run_lifecycle.py` | ctx、tools_override、event_log、租户键 |
| `adapters/langgraph_runtime.py` | configurable 合并 RUN_CONTEXT + thread_id 存储键 |
| `apps/api/auth/run_context.py` | claims → RunContext |
| `apps/api/routes/{chat,threads,runs}.py` | HTTP |
| `scripts/replay_run.py` | 回放 |
| `LICENSE`、`.cursorrules`、`docs/ai-instructions/*`、`scripts/check_ai_instructions.sh` | M1 |

---

### Task 1: M1 — LICENSE + AI 指令 + CI 检查

**Files:**
- Create: `LICENSE`（MIT）
- Create: `.cursorrules`、`CLAUDE.md`、`AGENTS.md`
- Create: `docs/ai-instructions/00-project-overview.md` … `04-testing.md`
- Create: `scripts/check_ai_instructions.sh`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- 入口文件仅 5 条 MUST（v4.1 §10.1 前 5 条；第 6–7 条可写「见完整方案，M2+/M5 后强制」）
- `check_ai_instructions.sh`：解析入口中的 `docs/ai-instructions/*.md` 路径，缺失则 exit 1

- [ ] **Step 1: Write script that fails if overview missing**

```bash
# scripts/check_ai_instructions.sh
#!/usr/bin/env bash
set -euo pipefail
test -f docs/ai-instructions/00-project-overview.md
test -f docs/ai-instructions/01-architecture-rules.md
```

- [ ] **Step 2: Add MIT LICENSE + short AI entry files pointing to docs/ai-instructions/**

- [ ] **Step 3: Run `bash scripts/check_ai_instructions.sh`；CI 增加一步**

- [ ] **Step 4: Commit**

```bash
git add LICENSE .cursorrules CLAUDE.md AGENTS.md docs/ai-instructions \
  scripts/check_ai_instructions.sh .github/workflows/ci.yml
git commit -m "docs: add MIT license and AI instruction gates (M1)"
```

---

### Task 2: RunContext + checkpoint_thread_key

**Files:**
- Create: `packages/core/src/agentbridge_core/protocol/context.py`
- Create: `packages/core/tests/protocol/test_context.py`

**Interfaces:**
- `RUN_CONTEXT_KEY = "run_context"`
- `RunContext` 字段同 v4.1 §4.1
- `get_run_context(config: Mapping | None) -> RunContext`
- `checkpoint_thread_key(tenant_id: str, thread_id: str) -> str`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/protocol/test_context.py
from agentbridge_core.protocol.context import (
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
```

- [ ] **Step 2: Run** `python -m pytest packages/core/tests/protocol/test_context.py -v` → FAIL

- [ ] **Step 3: Implement**（与 v4.1 字段一致的 BaseModel + helpers）

- [ ] **Step 4: Run** → PASS

- [ ] **Step 5: Commit** `feat(core): add RunContext and checkpoint_thread_key`

---

### Task 3: PolicyEngine + tool_meta（list + invoke 语义）

**Files:**
- Create: `packages/core/src/agentbridge_core/ports/policy.py`
- Create: `packages/core/src/agentbridge_core/registry/tool_meta.py`
- Create: `packages/core/src/agentbridge_core/adapters/role_policy.py`
- Create: `packages/core/src/agentbridge_core/adapters/noop_policy.py`
- Create: `packages/core/tests/adapters/test_role_policy.py`

**Interfaces:**
- `decide` / `filter_tools` 同 v4.1；本 plan 只实现 `list_tools`/`invoke_tool` 的 allow|deny（`require_approval`/`mask` 留给 Plan4，decide 遇未知 action 返回 `deny`）
- `attach_tool_meta` / `get_tool_meta`
- `*` in permissions → allow

- [ ] **Step 1: Failing tests**（viewer 滤掉 admin tool；invoke deny；`*` allow）— 同前版 `test_role_policy.py`

- [ ] **Step 2–4: Implement RolePolicyEngine + meta + PASS**

- [ ] **Step 5: Commit** `feat(core): RolePolicyEngine for list_tools and invoke_tool`

---

### Task 4: AuditLogger

**Files:**
- Create: `ports/audit_logger.py`、`adapters/memory_audit_logger.py`、`adapters/noop_audit_logger.py`
- Create: `packages/core/tests/adapters/test_memory_audit_logger.py`

- [ ] TDD MemoryAuditLogger（`records` 列表）+ Commit `feat(core): AuditLogger port`

---

### Task 5: RequestPipeline + ToolPolicyPlugin（仅 list 过滤）

**Files:**
- Create: `packages/core/src/agentbridge_core/application/pipeline.py`
- Create: `packages/core/tests/application/test_pipeline.py`
- Modify: `packages/core/src/agentbridge_core/public.py`
- Modify: `packages/core/src/agentbridge_core/application/run_lifecycle.py` — 增加 `ctx`、`tools_override`（invoke 包装在 T6）

**Interfaces:**
- `ToolPolicyPlugin(policy, audit, tools_registry)` — **三参数缺一不可**
- `RequestPipeline(lifecycle, plugins)`
- `public.orchestration_stream(target, **kwargs)`：有 `handle` 则调用，否则 `start_stream`

- [ ] **Step 1: Write the failing test**（注意 FakeRuntime 签名为 `async def astream(self, builder, **kwargs)`）

```python
# packages/core/tests/application/test_pipeline.py
from types import SimpleNamespace

import pytest
from agentbridge_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agentbridge_core.adapters.inprocess_lock import InProcessThreadLock
from agentbridge_core.adapters.memory_audit_logger import MemoryAuditLogger
from agentbridge_core.adapters.noop_hooks import NoopHooks
from agentbridge_core.adapters.role_policy import RolePolicyEngine
from agentbridge_core.application.pipeline import RequestPipeline, ToolPolicyPlugin
from agentbridge_core.application.run_lifecycle import RunLifecycle
from agentbridge_core.protocol.context import RunContext
from agentbridge_core.registry.input_builders import InputBuilderRegistry
from agentbridge_core.registry.tool_meta import attach_tool_meta
from conftest import FakeCheckpointerFactory, FakeRuntime


class CapturingRuntime(FakeRuntime):
    def __init__(self) -> None:
        self.last_tools = None

    async def astream(self, builder, **kwargs):
        self.last_tools = kwargs.get("tools")
        async for frag in super().astream(builder, **kwargs):
            yield frag


@pytest.mark.asyncio
async def test_pipeline_filters_tools(graphs, tools, queue_and_sink, drain_events):
    admin_tool = attach_tool_meta(SimpleNamespace(name="delete"), required_roles=["admin"])
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
```

- [ ] **Step 2: Run** → FAIL

- [ ] **Step 3: Implement pipeline；lifecycle.start_stream 增加 `ctx`/`tools_override`；取 tool 时 `tools_override if not None else registry`**

`ToolPolicyPlugin.before_run`：`filter_tools` → `req.tools_override`；audit `list_tools`。

- [ ] **Step 4: Run** pipeline + 旧 lifecycle 测试 → PASS

- [ ] **Step 5: Commit** `feat(core): RequestPipeline with ToolPolicyPlugin`

---

### Task 6: invoke 双检 + RunContext 注入 + 租户化 checkpointer 键

**Files:**
- Create: `packages/core/src/agentbridge_core/application/tool_guard.py`
- Create: `packages/core/tests/application/test_tool_guard.py`
- Modify: `run_lifecycle.py` — 创建 run_id 后 `ctx.model_copy(update={...})`；调用 `guard_tools`
- Modify: `adapters/langgraph_runtime.py` — `config["configurable"]` 合并：
  - `thread_id` = `checkpoint_thread_key(tenant_id, api_thread_id)`（tenant 缺省用 `""` 时键为 `::{thread}` **禁止**；无 tenant 时用 `"default"`）
  - `RUN_CONTEXT_KEY` = ctx.model_dump()
- Create: `packages/core/tests/adapters/test_langgraph_runtime_config.py`（可单测纯函数 `build_run_config`）

**Interfaces:**
```python
def guard_tools(
    tools: list[Any],
    *,
    policy: PolicyEngine,
    ctx: RunContext,
    audit: AuditLogger | None = None,
) -> list[Any]:
    """Wrap each tool so invoke_tool is decided before the underlying call."""
```

包装策略（LangChain StructuredTool）：优先 `tool.coroutine` / `tool.func` 外包；deny 时返回 `{"ok": False, "error": "forbidden"}` 字符串或抛 `PermissionError`（**选定：返回 ToolMessage 友好字符串 `"forbidden"` 并 audit result=denied**，避免弄崩图）。

- [ ] **Step 1: Failing test**

```python
# packages/core/tests/application/test_tool_guard.py
from types import SimpleNamespace
import pytest
from agentbridge_core.adapters.role_policy import RolePolicyEngine
from agentbridge_core.application.tool_guard import guard_tools
from agentbridge_core.protocol.context import RunContext
from agentbridge_core.registry.tool_meta import attach_tool_meta


class _T:
    name = "delete"
    def invoke(self, args):
        return "did-delete"


@pytest.mark.asyncio
async def test_guard_denies_invoke_for_viewer():
    raw = attach_tool_meta(_T(), required_roles=["admin"])
    # If using SimpleNamespace, implement a minimal invoker protocol in tool_guard tests
    ctx = RunContext(roles=["viewer"], tenant_id="t")
    guarded = guard_tools([raw], policy=RolePolicyEngine(), ctx=ctx)
    # call the guarded invoke path — exact API depends on implementation;
    # assert underlying did-delete never happens (set flag on _T)
```

实现时让 `_T.invoke` 设 `self.called=True`；deny 后 `called is False`。

- [ ] **Step 3: Implement `guard_tools` + lifecycle**

Lifecycle 在 `try_acquire` **之前**计算：

```python
storage_key = checkpoint_thread_key(ctx.tenant_id or "default", thread_id)
```

随后：`locks.try_acquire(storage_key, run_id)` / `release(storage_key, run_id)`；`cancels` 若按 thread 索引，同样用 `storage_key`（或并行存 api_thread_id 映射——**选定：cancel API 仍收裸 thread_id，宿主先算 storage_key 再调 cancel**）。

`extra` 传入 runtime：`run_context`、`api_thread_id`、`storage_key`。

- [ ] **Step 3: Extract `build_graph_config(thread_id, ctx) -> dict` 并单测租户键**

```python
def build_graph_config(*, thread_id: str, ctx: RunContext) -> dict:
    tenant = ctx.tenant_id or "default"
    return {
        "configurable": {
            "thread_id": checkpoint_thread_key(tenant, thread_id),
            RUN_CONTEXT_KEY: ctx.model_dump(),
        }
    }
```

`langgraph_runtime.astream` 使用 `extra["graph_config"]` 或自行从 `extra["run_context"]` 构建——**Lifecycle 负责放入 `extra["run_context"]=ctx` 与 `extra["api_thread_id"]=thread_id`**。

- [ ] **Step 4: PASS + Commit** `feat(core): invoke_tool guard and tenant checkpoint keys`

---

### Task 7: API 接线 + M2a 验收

**Files:**
- Create: `apps/api/auth/run_context.py`
- Modify: `lifespan.py`、`deps.py`、`routes/chat.py`
- Modify: `apps/api/domains/demo_tools/tools.py` — `attach_tool_meta` 给受限 tool（可增加 `delete_records` 仅注册不强制图调用）
- Create: `apps/api/tests/test_tool_policy_matrix.py`
- Create: `apps/api/tests/test_claims_to_run_context.py`

**Interfaces:**
- `claims_to_run_context(claims, *, auth_required)` 同 v4.1
- `app.state.pipeline` + `get_pipeline`
- chat：`ctx = claims_to_run_context(...); orchestration_stream(pipeline, ..., ctx=ctx)`

- [ ] **Step 1–4: TDD claims + matrix + wire + PASS**

- [ ] **Step 5: Commit** `feat(api): wire pipeline RunContext and policy (M2a)`

**M2a 验收条件：** viewer/admin 矩阵绿；list 审计有记录；invoke deny 单测绿。

---

### Task 8: EventLog + append-before-emit（M2b）

**Files:**
- Create: `ports/event_log.py`、`adapters/memory_event_log.py`
- Create: `tests/adapters/test_memory_event_log.py`
- Create: `tests/application/test_event_log_emit_order.py`
- Modify: `run_lifecycle.py` — 构造注入 `event_log: EventLog | None = None`

**钉死保留策略（对齐 v4.1 §4.2）：**
- MemoryEventLog：**全量**已提交信封（含每条 text_delta）
- append 失败：不再 `sink.emit` 该事件；emit `error`（若 start 已提交）并终止

- [ ] **Step 1: Failing tests** — append/list；FailingEventLog 下无 `text_delta` 出站

```python
class FailingEventLog:
    async def append(self, run_id: str, event: dict) -> None:
        raise RuntimeError("append failed")
    async def list(self, run_id: str) -> list[dict]:
        return []
```

- [ ] **Step 2: Implement emit 路径**

```python
if self._event_log is not None:
    await self._event_log.append(run_id, evt)
await sink.emit(evt)
```

对 start/done/error/cancel/fragment 一律遵守。

- [ ] **Step 3: PASS + Commit** `feat(core): EventLog append-before-emit`

---

### Task 9: MessageStore + RunStore + 终端投影

**Files:**
- Create: `ports/message_store.py`、`ports/run_store.py`
- Create: `adapters/memory_message_store.py`、`adapters/memory_run_store.py`
- Create: `application/project_turn.py` — `async def project_turn(...)`
- Create: `tests/adapters/test_memory_stores.py`、`tests/application/test_project_turn.py`
- Modify: lifecycle `finally`/终端分支或 `ProjectionHooks` 调用 `project_turn`
- Modify: lifespan 注入

**Interfaces:**
```python
async def project_turn(
    *,
    event_log: EventLog,
    message_store: MessageStore,
    run_store: RunStore,
    tenant_id: str,
    thread_id: str,
    run_id: str,
    query: str,
    terminal: str,
) -> None: ...
```

投影规则：user 一条 = query；assistant = 拼接所有已提交 `text_delta.data.content`；附 tool_call/tool_result 摘要列表（可选字段 `tool_trace`）。

跨租户：`list_messages("other", thread_id) == []`。

- [ ] TDD + Commit `feat(core): message/run projection after terminal`

---

### Task 10: REST + replay（M2b 验收）

**Files:**
- Create: `apps/api/routes/threads.py`、`apps/api/routes/runs.py`
- Modify: `main.py`
- Create: `apps/api/tests/test_threads_and_events.py`
- Create: `packages/core/src/agentbridge_core/application/replay.py`
- Create: `scripts/replay_run.py`（读 env/DSN 或测试只测 `replay.py`）

**Endpoints（对齐 contracts）：**
- `GET /threads`
- `GET /threads/{id}/messages`
- `GET /runs/{id}`
- `GET /runs/{id}/events`

租户来自 RunContext（dev 默认 `dev`）。

- [ ] **Step 1: TestClient** — fake runtime stream 后 messages/events 非空

- [ ] **Step 2: Implement routes**

- [ ] **Step 3: Commit** `feat(api): threads/runs/events and replay (M2b)`

**M2b 验收条件：** messages 可查；events=EventLog；append 失败测试仍绿。

---

### Task 11: 回归

```bash
python -m pytest packages/core/tests apps/api/tests -v
lint-imports
python scripts/import_scan_core.py
bash scripts/check_ai_instructions.sh
```

- [ ] Update `docs/roadmap.md`：M1/M2a/M2b 状态
- [ ] Commit `chore: Plan1 acceptance green`

## 不在本 Plan

DataSource（Plan2）、ready/metrics/限流（Plan3）、Gateway/HIL/RAG（Plan4）、多 Agent/SDK/Redis（Plan5）。  
Postgres EventLog 表：可另开 follow-up；v0.2 以 Memory 验收。
