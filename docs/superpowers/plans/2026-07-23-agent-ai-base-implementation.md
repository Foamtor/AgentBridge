# AgentBridge 全栈本平台 Implementation Plan

> **阅读提示：** 这是历史设计/实施记录。文中若仍有偏内部的说法，请以仓库根目录 README、docs/roadmap.md、docs/add-a-domain.md 的白话为准。\n\n> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地可复用的 AI 业务本平台：分层编排内核 + FastAPI 宿主 + OIDC + React 调试台 + echo 域，行为对齐产品仓契约且代码绿场重写。

**Architecture:** `packages/core`（application / ports / adapters / registry / protocol）由 `apps/api/lifespan.py` 组装注入；业务只通过 `domains/*` 注册；Web 调试台消费稳定 SSE。禁止 core import domains，禁止照抄 RAG_Agent 实现。

**Tech Stack:** Python 3.12+、FastAPI、LangGraph、Pydantic v2、Postgres（checkpointer）、Authentik OIDC（可选）、React 18 + Vite + TS、import-linter、pytest、pytest-asyncio。

## Global Constraints

- 绿场重写：禁止大段复制 `RAG_Agent/agent_core/orchestration/` 或业务包
- 依赖方向：`application` → 仅 `ports` / `registry` / `protocol`；adapters 仅在 `apps/api/lifespan.py` 里 `new`
- `public.py` 只转发已注入的 `RunLifecycle`，禁止在此 `new` 适配器
- SSE/HTTP 以 `docs/contracts.md` 为准；对照 `docs/parity-with-product.md`
- 目录以 `docs/superpowers/specs/2026-07-23-code-structure.md` 为准，不另开树
- 路径一律写仓库相对全路径（如 `packages/core/src/agentbridge_core/...`）
- CI：仓库根 `lint-imports` + `python scripts/import_scan_core.py` 必须绿
- 本地 smoke **不要求** Authentik 必起；PG 可先 Memory checkpointer，compose PG 在 Task 11

## Already done（不要重做）

- [x] 目录骨架、`.importlinter`、architecture-gates CI、`import_scan_core.py`
- [x] `apps/api` hatch 可安装；core 含 langgraph 依赖
- [x] `docs/contracts.md` 字段级样例；`docs/parity-with-product.md` 初稿
- [x] `registry/input_builders.py` 占位；specs §19 审阅修复

## Dev dependency note

在第一次跑 async 测试前，把 `pytest-asyncio>=0.24` 写入 `packages/core/pyproject.toml` 的 `[project.optional-dependencies].dev`，并：

```bash
pip install -e "packages/core[dev]"
```

`pyproject.toml` 增加：

```toml
# under [project.optional-dependencies] dev =
"pytest-asyncio>=0.24",
```

并在 `packages/core/tests/conftest.py`（或 `pyproject.toml`）设：

```python
# packages/core/tests/conftest.py
pytest_plugins = []  # optional
```

```toml
# packages/core/pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

---

### Task 1: Protocol events 对齐 contracts

**Files:**
- Modify: `packages/core/src/agentbridge_core/protocol/events.py`
- Modify: `packages/core/src/agentbridge_core/protocol/sse.py`
- Modify: `packages/core/tests/protocol/test_sse.py`
- Modify: `packages/core/pyproject.toml`（补 pytest-asyncio + pytest ini）
- Modify: `packages/core/tests/conftest.py`（可空文件占位）

**Interfaces:**
- Produces: `EVENT_TYPES: frozenset[str]`
- Produces: `build_event(type: str, *, run_id: str, sequence: int, trace_id: str, data: dict | None = None, step: str | None = None, status: str | None = None) -> dict`
  - 返回 **dict**（与 contracts SSE JSON 一致）；不强制对外暴露 Pydantic 模型名 `OutboundEvent`（若内部用 BaseModel，序列化后仍以 dict 出站）
- Produces: `format_sse_line(event: dict) -> str`（`data: {json}\n\n`）

- [ ] **Step 1: 写入 pytest-asyncio 与 ini，重装 core[dev]**

- [ ] **Step 2: 写失败测试**

```python
# packages/core/tests/protocol/test_sse.py
from agentbridge_core.protocol.events import build_event, EVENT_TYPES
from agentbridge_core.protocol.sse import format_sse_line

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
        "start", "step_update", "text_delta", "tool_call", "tool_result",
        "done", "error", "cancel_requested", "cancelled",
    }
    assert required <= EVENT_TYPES
```

- [ ] **Step 3: 跑测确认失败**

Run: `pytest packages/core/tests/protocol/test_sse.py -v`  
Expected: FAIL（符号未实现）

- [ ] **Step 4: 实现 `build_event` / `EVENT_TYPES` / `format_sse_line`（对齐 docs/contracts.md §2）**

- [ ] **Step 5: 跑测通过**

Run: `pytest packages/core/tests/protocol/test_sse.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add packages/core/pyproject.toml packages/core/src/agentbridge_core/protocol packages/core/tests
git commit -m "feat(core): add SSE event protocol aligned with contracts"
```

---

### Task 2: Ports + Registries + errors

**Files:**
- Modify: `packages/core/src/agentbridge_core/ports/thread_lock.py`
- Modify: `packages/core/src/agentbridge_core/ports/event_sink.py`
- Modify: `packages/core/src/agentbridge_core/ports/checkpointer.py`
- Modify: `packages/core/src/agentbridge_core/ports/graph_runtime.py`
- Modify: `packages/core/src/agentbridge_core/ports/run_control.py`
- Modify: `packages/core/src/agentbridge_core/ports/hooks.py`
- Modify: `packages/core/src/agentbridge_core/registry/graphs.py`
- Modify: `packages/core/src/agentbridge_core/registry/tools.py`
- Modify: `packages/core/src/agentbridge_core/registry/input_builders.py`
- Modify: `packages/core/src/agentbridge_core/application/errors.py`
- Modify: `packages/core/tests/registry/test_registries.py`

**Interfaces:**
- `ThreadLock`: `async try_acquire(thread_id, run_id) -> bool`, `async release(thread_id, run_id) -> None`
- `EventSink`: `async emit(event: dict) -> None`, `async close() -> None`
- `CheckpointerFactory`: `async setup()`, `async get()`, `async teardown()`
- `GraphRuntime`: `async astream(builder, *, tools, checkpointer, thread_id, query, cancel_token, extra=None)` → `AsyncIterator[dict]`
- `RunCancelRegistry`: `async register(thread_id, run_id, token)`, `async request_cancel(thread_id, run_id=None) -> bool`, `async unregister(thread_id, run_id)`
- `RunHooks`: `async on_run_end(payload: dict) -> None`
- `GraphRegistry` / `ToolRegistry` / `InputBuilderRegistry`: `register(key, value)`, `get(key)`；未知 key → `UnknownRoute`
- Errors: `ThreadBusy`, `UnknownRoute`, `RunNotFound`（都是 `Exception` 子类）

- [ ] **Step 1: 写失败测试**

```python
# packages/core/tests/registry/test_registries.py
import pytest
from agentbridge_core.registry.graphs import GraphRegistry
from agentbridge_core.registry.tools import ToolRegistry
from agentbridge_core.registry.input_builders import InputBuilderRegistry
from agentbridge_core.application.errors import UnknownRoute

def test_graph_registry_get_unknown():
    with pytest.raises(UnknownRoute):
        GraphRegistry().get("missing")

def test_graph_registry_roundtrip():
    reg = GraphRegistry()
    reg.register("echo", lambda **kw: "graph")
    assert reg.get("echo")() == "graph"

def test_tool_and_input_builder_registries():
    tools = ToolRegistry()
    tools.register("echo", [])
    assert tools.get("echo") == []
    ib = InputBuilderRegistry()
    ib.register("echo", lambda q, **kw: {"messages": [q]})
    assert "messages" in ib.get("echo")("hi")
```

- [ ] **Step 2: 跑测失败 → 实现 Protocol + 三个 Registry + errors → 跑通**

Run: `pytest packages/core/tests/registry/test_registries.py -v`

- [ ] **Step 3: Commit**

```bash
git add packages/core/src/agentbridge_core/ports packages/core/src/agentbridge_core/registry packages/core/src/agentbridge_core/application/errors.py packages/core/tests/registry
git commit -m "feat(core): add ports, registries, and application errors"
```

---

### Task 3: In-process lock + cancel + NoopHooks

**Files:**
- Modify: `packages/core/src/agentbridge_core/adapters/inprocess_lock.py`
- Modify: `packages/core/src/agentbridge_core/adapters/inprocess_cancel.py`
- Modify: `packages/core/src/agentbridge_core/adapters/noop_hooks.py`
- Modify: `packages/core/tests/adapters/test_inprocess_lock.py`

**Interfaces:**
- `InProcessThreadLock` 实现 `ThreadLock`
- `InProcessCancelRegistry` 实现 `RunCancelRegistry`（可用 `asyncio.Event` 作 token）
- `NoopHooks.on_run_end` 空实现

- [ ] **Step 1: 写失败测试**

```python
# packages/core/tests/adapters/test_inprocess_lock.py
import pytest
from agentbridge_core.adapters.inprocess_lock import InProcessThreadLock
from agentbridge_core.adapters.inprocess_cancel import InProcessCancelRegistry

@pytest.mark.asyncio
async def test_lock_busy():
    lock = InProcessThreadLock()
    assert await lock.try_acquire("t1", "r1") is True
    assert await lock.try_acquire("t1", "r2") is False
    await lock.release("t1", "r1")
    assert await lock.try_acquire("t1", "r3") is True

@pytest.mark.asyncio
async def test_cancel_registry():
    reg = InProcessCancelRegistry()
    token = object()
    await reg.register("t1", "r1", token)
    assert await reg.request_cancel("t1", "r1") is True
    await reg.unregister("t1", "r1")
    assert await reg.request_cancel("t1", "r1") is False
```

- [ ] **Step 2: 实现 → pytest 通过**

Run: `pytest packages/core/tests/adapters/test_inprocess_lock.py -v`

- [ ] **Step 3: Commit**

```bash
git add packages/core/src/agentbridge_core/adapters packages/core/tests/adapters
git commit -m "feat(core): add in-process thread lock and cancel registry"
```

---

### Task 4: Memory checkpointer + SseEventSink + event_mapper（可测最小集）

**Files:**
- Modify: `packages/core/src/agentbridge_core/adapters/memory_checkpointer.py`
- Modify: `packages/core/src/agentbridge_core/adapters/sse_event_sink.py`
- Modify: `packages/core/src/agentbridge_core/adapters/event_mapper.py`
- Modify: `packages/core/tests/adapters/test_event_mapper.py`

**Interfaces:**
- `MemoryCheckpointerFactory.setup/get/teardown`
- `SseEventSink(queue: asyncio.Queue)`：`emit` put dict；`close` put `None` 哨兵
- `map_text_delta(content: str, *, run_id, sequence, trace_id) -> dict`（type=`text_delta`）
- `map_tool_call(name, args, tool_call_id, *, run_id, sequence, trace_id) -> dict`
- 完整 LangGraph `astream_events` 分支在 Task 5 的 `LangGraphRuntime` 内调用上述函数

- [ ] **Step 1: 写失败测试**

```python
import asyncio
import pytest
from agentbridge_core.adapters.sse_event_sink import SseEventSink
from agentbridge_core.adapters.event_mapper import map_text_delta

@pytest.mark.asyncio
async def test_sse_sink_emit_and_close():
    q: asyncio.Queue = asyncio.Queue()
    sink = SseEventSink(q)
    await sink.emit({"type": "start"})
    await sink.close()
    assert (await q.get())["type"] == "start"
    assert await q.get() is None

def test_map_text_delta():
    evt = map_text_delta("hi", run_id="r1", sequence=2, trace_id="tr1")
    assert evt["type"] == "text_delta"
    assert evt["data"]["content"] == "hi"
```

- [ ] **Step 2: 实现 MemoryCheckpointerFactory（可用 langgraph MemorySaver）+ sink + mapper → 测试绿**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(core): add memory checkpointer, sse sink, event mapper helpers"
```

---

### Task 5: LangGraphRuntime + RunLifecycle + public 门面

**Files:**
- Modify: `packages/core/src/agentbridge_core/adapters/langgraph_runtime.py`
- Modify: `packages/core/src/agentbridge_core/application/run_lifecycle.py`
- Modify: `packages/core/src/agentbridge_core/public.py`
- Modify: `packages/core/tests/application/test_run_lifecycle.py`
- Modify: `packages/core/tests/conftest.py`（fixtures）

**Interfaces:**
- `RunLifecycle.__init__(locks, checkpointers, graphs, tools, input_builders, runtime, cancels, hooks)`
- `async start_stream(*, query, thread_id, route, sink, model=None, extra=None) -> None`
- `async cancel(*, thread_id, run_id=None) -> None`（无 run → `RunNotFound`）
- `orchestration_stream(lifecycle, **kwargs)` / `cancel_run(lifecycle, **kwargs)` 仅转发

行为（必须）：
1. `try_acquire` 失败 → `ThreadBusy`
2. `graphs.get(route)`；`tools.get(route)`（无注册工具则 `[]` 若 ToolRegistry 允许；或与 graph 同 key 必注册空列表）
3. `build_event("start", ...)` → `sink.emit`
4. `cancels.register` → `async for evt in runtime.astream(...)` → `sink.emit(evt)`
5. 正常结束 `done`；取消路径 `cancel_requested` + `cancelled`
6. `finally`: `hooks.on_run_end` + `release` + `unregister` + `sink.close`

- [ ] **Step 1: 在 conftest 写 fixtures（假 runtime / queue sink）**

```python
# packages/core/tests/conftest.py
import asyncio
import pytest
from agentbridge_core.adapters.inprocess_lock import InProcessThreadLock
from agentbridge_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agentbridge_core.adapters.noop_hooks import NoopHooks
from agentbridge_core.adapters.sse_event_sink import SseEventSink
from agentbridge_core.registry.graphs import GraphRegistry
from agentbridge_core.registry.tools import ToolRegistry
from agentbridge_core.registry.input_builders import InputBuilderRegistry
from agentbridge_core.protocol.events import build_event

class FakeCheckpointerFactory:
    async def setup(self): ...
    async def get(self):
        return None
    async def teardown(self): ...

class FakeRuntime:
    async def astream(self, builder, **kwargs):
        yield build_event("text_delta", run_id="r-test", sequence=2, trace_id="tr", data={"content": "ok"})

@pytest.fixture
def graphs():
    g = GraphRegistry()
    g.register("echo", lambda **kw: object())
    return g

@pytest.fixture
def tools():
    t = ToolRegistry()
    t.register("echo", [])
    return t

@pytest.fixture
async def queue_and_sink():
    q: asyncio.Queue = asyncio.Queue()
    return q, SseEventSink(q)

async def drain(q: asyncio.Queue) -> list[dict]:
    out = []
    while True:
        item = await q.get()
        if item is None:
            break
        out.append(item)
    return out
```

- [ ] **Step 2: 写失败测试**

```python
# packages/core/tests/application/test_run_lifecycle.py
import pytest
from agentbridge_core.application.run_lifecycle import RunLifecycle
from agentbridge_core.application.errors import ThreadBusy
from agentbridge_core.adapters.inprocess_lock import InProcessThreadLock
from agentbridge_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agentbridge_core.adapters.noop_hooks import NoopHooks
from agentbridge_core.registry.input_builders import InputBuilderRegistry
from packages.core.tests.conftest import (  # prefer relative imports from conftest fixtures instead
    FakeCheckpointerFactory, FakeRuntime, drain,
)

# Use fixtures from conftest — wire lifecycle in test:

@pytest.mark.asyncio
async def test_start_stream_emits_start_and_done(graphs, tools, queue_and_sink):
    q, sink = queue_and_sink
    lc = RunLifecycle(
        locks=InProcessThreadLock(),
        checkpointers=FakeCheckpointerFactory(),
        graphs=graphs,
        tools=tools,
        input_builders=InputBuilderRegistry(),
        runtime=FakeRuntime(),
        cancels=InProcessCancelRegistry(),
        hooks=NoopHooks(),
    )
    await lc.start_stream(query="hi", thread_id="t1", route="echo", sink=sink)
    types = [e["type"] for e in await drain(q)]
    assert types[0] == "start"
    assert types[-1] == "done"

@pytest.mark.asyncio
async def test_thread_busy(graphs, tools, queue_and_sink):
    q, sink = queue_and_sink
    locks = InProcessThreadLock()
    await locks.try_acquire("t1", "other")
    lc = RunLifecycle(
        locks=locks,
        checkpointers=FakeCheckpointerFactory(),
        graphs=graphs,
        tools=tools,
        input_builders=InputBuilderRegistry(),
        runtime=FakeRuntime(),
        cancels=InProcessCancelRegistry(),
        hooks=NoopHooks(),
    )
    with pytest.raises(ThreadBusy):
        await lc.start_stream(query="hi", thread_id="t1", route="echo", sink=sink)
```

（实现时把 `Fake*` 放进 `conftest.py`，测试内不要错误 import `packages.core.tests`。）

- [ ] **Step 3: 实现 `RunLifecycle` + `LangGraphRuntime` 最小版（可先委托 Fake 同构接口；真实 astream_events 映射 text_delta）+ `public` 转发**

- [ ] **Step 4: pytest 通过**

Run: `pytest packages/core/tests/application/test_run_lifecycle.py -v`

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/agentbridge_core/adapters/langgraph_runtime.py packages/core/src/agentbridge_core/application/run_lifecycle.py packages/core/src/agentbridge_core/public.py packages/core/tests
git commit -m "feat(core): implement RunLifecycle stream/cancel with graph runtime"
```

---

### Task 6: API host — settings / health / lifespan（bootstrap 先空）

**Files:**
- Modify: `apps/api/config/settings.py`
- Modify: `apps/api/config/logging.py`
- Modify: `apps/api/main.py`
- Modify: `apps/api/lifespan.py`
- Modify: `apps/api/deps.py`
- Modify: `apps/api/routes/health.py`
- Modify: `apps/api/domains/bootstrap.py`（**先空**：`register_all` 不 import echo）
- Modify: `apps/api/tests/test_health.py`

**Interfaces:**
- `Settings`: `auth_required: bool = False`, `pg_host/port/database/user/password`, `oidc_issuer`, `oidc_audience`, `llm_api_key`, `use_memory_checkpointer: bool = True`
- `create_app() -> FastAPI`
- `get_run_lifecycle(request) -> RunLifecycle`
- lifespan：组装 lock/cancel/memory CP/registries/`register_all`（空）/`RunLifecycle` → `app.state.run_lifecycle`

**顺序约束：** 本 Task **禁止** `from apps.api.domains.echo import ...`。echo 在 Task 8 再挂上。

- [ ] **Step 1: 写 health 测试**

```python
# apps/api/tests/test_health.py
from fastapi.testclient import TestClient
from main import create_app

def test_health():
    with TestClient(create_app()) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
```

- [ ] **Step 2: 实现 settings / create_app / lifespan / health → 测试绿**

Run: `cd apps/api && pytest tests/test_health.py -v`

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(api): wire create_app, lifespan injection, health route"
```

---

### Task 7: Chat stream/cancel + 错误映射（用 test double 图，不依赖 echo 包）

**Files:**
- Modify: `apps/api/routes/chat.py`
- Modify: `apps/api/routes/schemas.py`
- Modify: `apps/api/tests/test_chat_stream.py`
- Modify: `apps/api/tests/test_chat_cancel.py`
- Modify: `apps/api/tests/conftest.py`

**Interfaces:**
- 请求/响应严格按 `docs/contracts.md`
- `ThreadBusy` → 409 + `thread_busy`
- `UnknownRoute` → 400 + `unknown_route`
- `RunNotFound` → 404 + `run_not_found`

**测试策略（写死）：** 在 `conftest.py` fixture 里对 `app.state` 的 registries **手动** `register("echo", fake_builder)`，**不** import `domains.echo`。

- [ ] **Step 1: conftest 提供挂好 double 的 TestClient**

```python
# apps/api/tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from main import create_app
from agentbridge_core.protocol.events import build_event

class ApiFakeRuntime:
    async def astream(self, builder, **kwargs):
        yield build_event("text_delta", run_id="r-x", sequence=2, trace_id="tr", data={"content": "ok"})

@pytest.fixture
def client():
    app = create_app()
    # After lifespan, replace runtime or register graph on app.state —
    # simplest: in lifespan test mode env AGENTBRIDGE_TEST=1 register stub.
    with TestClient(app) as c:
        graphs = c.app.state.run_lifecycle._graphs
        tools = c.app.state.run_lifecycle._tools
        graphs.register("echo", lambda **kw: object())
        tools.register("echo", [])
        c.app.state.run_lifecycle._runtime = ApiFakeRuntime()
        yield c
```

（若不愿碰私有属性：为 `RunLifecycle` 增加测试用 `replace_runtime` 或 lifespan 读 `AGENTBRIDGE_FAKE_RUNTIME=1`。选一种写进实现，测试只走公开路径更佳。）

- [ ] **Step 2: stream 返回 SSE 含 start/done；二次同 thread 并发测 409**

- [ ] **Step 3: cancel 测 200 / 404**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(api): add chat stream and cancel endpoints with contract errors"
```

---

### Task 8: Echo domain + 接入 bootstrap

**Files:**
- Modify: `apps/api/domains/echo/state.py`
- Modify: `apps/api/domains/echo/tools.py`
- Modify: `apps/api/domains/echo/graph.py`
- Modify: `apps/api/domains/echo/bootstrap.py`
- Modify: `apps/api/domains/bootstrap.py`（此处才 `import echo`）
- Modify: `apps/api/tests/test_chat_stream.py`（增加真实 echo 用例，可与 fake 分开关）

**Interfaces:**
- `route="echo"`；`echo` tool；类型化 State；`build_echo_graph(checkpointer, tools, ...)`
- `domains.bootstrap.register_all` 调用 `echo.bootstrap.register`

- [ ] **Step 1: 实现 echo 四件套 + bootstrap 注册**

- [ ] **Step 2: 集成测（可 `AGENTBRIDGE_FAKE_RUNTIME=0`）SSE 有 text 或 tool 事件 → done**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(api): add echo domain plugin and wire bootstrap"
```

---

### Task 9: Auth 开关

**Files:**
- Modify: `apps/api/auth/oidc.py`
- Modify: `apps/api/auth/middleware.py`
- Modify: `apps/api/auth/schemas.py`
- Modify: `apps/api/main.py`（挂中间件）
- Modify: `apps/api/tests/test_auth_optional.py`

- [ ] **Step 1: `AUTH_REQUIRED=false` 无 token 可 POST /chat/stream（或 health 以外受保护路由）**

- [ ] **Step 2: `AUTH_REQUIRED=true` 无 token → 401 `unauthorized`**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(api): optional OIDC bearer auth"
```

---

### Task 10: LoggingHooks 示例 + scaffold 注释

**Files:**
- Create: `packages/core/src/agentbridge_core/adapters/logging_hooks.py`（或 `apps/api` 下示例 hooks）
- Modify: `apps/api/domains/_scaffold/*`（State / recursion_limit 注释）
- Modify: `docs/add-a-domain.md`

- [ ] **Step 1: `LoggingHooks.on_run_end` 打结构化日志；文档说明如何在 lifespan 替换 NoopHooks**

- [ ] **Step 2: scaffold README 写清复制步骤**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: add LoggingHooks example and domain scaffold guidance"
```

---

### Task 11: Compose + start-dev + Postgres 开关

**Files:**
- Modify: `docker-compose.yml`（`postgres`, `redis`, `authentik` 服务；Authentik 可用 profile `auth`）
- Modify: `start-dev.ps1`, `start-dev.sh`, `stop-dev.ps1`, `stop-dev.sh`
- Modify: `packages/core/src/agentbridge_core/adapters/postgres_checkpointer.py`
- Modify: `apps/api/lifespan.py`（`use_memory_checkpointer` 切换）
- Modify: `.env.example`, `infra/authentik/README.md`

**验收：**
- 默认：`use_memory_checkpointer=true` 时 **不起 PG 也能** API+echo
- `docker compose up -d postgres` 健康后，可切 Postgres checkpointer
- Authentik：`docker compose --profile auth up -d`；**非** smoke 必过项

- [ ] **Step 1: 写 compose postgres 健康检查**

- [ ] **Step 2: 实现 PostgresCheckpointerFactory（依赖 `pip install -e "packages/core[postgres]"`）**

- [ ] **Step 3: start-dev 起 API + web（web 未就绪时可先只起 API）**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(infra): compose services, postgres checkpointer, start-dev"
```

---

### Task 12: React 调试台（拆分子步骤）

**Files:**
- Modify: `apps/web/package.json`（加 `react`, `react-dom`, `react-router-dom`, `vite`, `@vitejs/plugin-react`, `typescript`）
- Modify: `apps/web/vite.config.ts`, `tsconfig.json`, `index.html`
- Modify: `apps/web/src/main.tsx`, `App.tsx`, `routes/index.tsx`
- Modify: `apps/web/src/lib/apiBase.ts`, `sseClient.ts`
- Modify: `apps/web/src/features/auth/pkce.ts`, `token.ts`, `callback.tsx`
- Modify: `apps/web/src/features/debug/DebugPage.tsx`, `EventTimeline.tsx`, `SessionBar.tsx`, `SendPanel.tsx`
- Modify: `apps/web/src/features/contracts/ContractsPage.tsx`
- Modify: `apps/web/.env.example`

**UI：** 可用轻量原生 HTML/CSS 或 Ant Design；**不要**引入地图/OpenLayers。

- [ ] **Step 1: 补齐依赖，`pnpm install`，页面能打开空白壳**

- [ ] **Step 2: 实现 `sseClient.ts`**

```typescript
// 解析 data: JSON 行，按 type 回调；导出 type StableEventType 联合类型对齐 contracts
```

- [ ] **Step 3: auth — token 存取 + 可选手动粘贴 Bearer；PKCE 可第二迭代，先支持手动 token**

- [ ] **Step 4: DebugPage — thread_id、route=echo、发送、EventTimeline、Cancel、触发 409（连点两次）**

- [ ] **Step 5: ContractsPage — 列出稳定事件类型（可硬编码 contracts 表）**

- [ ] **Step 6: 与 API 联调 echo → 时间线出现 start…done**

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(web): add React debug console with SSE timeline"
```

---

### Task 13: 文档收口 + CI pytest/ruff + smoke + parity

**Files:**
- Modify: `docs/add-a-domain.md`, `docs/deploy.md`, `docs/architecture.md`, `README.md`（从零到绿）
- Modify: `.github/workflows/ci.yml`（加 `pytest packages/core`、`ruff check packages/core`）
- Modify: `scripts/smoke_echo.ps1`, `scripts/smoke_echo.sh`
- Modify: `docs/parity-with-product.md`（勾选可验证项）
- Optional: 产品仓加一句互链文档（P6.4，可跳过）

- [ ] **Step 1: CI 增加 pytest + ruff（需 `packages/core[dev]`）**

- [ ] **Step 2: smoke 脚本：health → stream → cancel → 同 thread 409**

- [ ] **Step 3: README「从零到绿」：clone → pip →（可选 compose）→ start-dev → 打开调试台**

- [ ] **Step 4: 本地用 `_scaffold` 复制为临时域验证「不改 core」；可不提交该域**

- [ ] **Step 5: Commit**

```bash
git commit -m "docs: finish runbooks; ci: pytest and ruff; test: echo smoke"
```

---

## P7（后置，不阻塞「模板可用」）

- Checkpoint TTL、OTel/Langfuse、HITL interrupt、多副本分布式锁、内部 pip 发包、产品仓是否迁同一核心、异步 worker

---

## Plan self-review（修订后）

| Spec 要求 | Task |
|-----------|------|
| contracts / 409 / cancel / auth | 1, 5, 7, 9, 13 |
| ports / adapters / lifecycle / public | 2–5 |
| echo 域 | 8（在 6 空 bootstrap 之后） |
| LoggingHooks / scaffold | 10 |
| compose / start-dev / PG | 11 |
| React 调试台 | 12（已拆步） |
| CI / smoke / parity / README | 13 |
| P7 | 文末 |

**本修订相对上一版：**

1. Task 6 bootstrap **空实现**，echo 延后到 Task 8，消除 import 断裂  
2. Task 7 **强制 test double**，不依赖 echo 包  
3. Task 5/7/12 补全可执行步骤与 fixture 约定  
4. 统一全路径；`build_event -> dict`  
5. 增加 `pytest-asyncio`；LoggingHooks（Task 10）；Authentik 非 smoke 必过  
6. 原 Task 8 auth → Task 9；infra → Task 11；web → Task 12；收口 → Task 13  
