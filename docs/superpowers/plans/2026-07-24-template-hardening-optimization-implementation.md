# Template Hardening + Production Readiness Implementation Plan

> **阅读提示：** 这是历史设计/实施记录。文中若仍有偏内部的说法，请以仓库根目录 README、docs/roadmap.md、docs/add-a-domain.md 的白话为准。\n\n> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 按修订规格完成一期模板硬化（契约单源、OutboundFragment、Option B builders、tool_result、demo_tools、服务启动时的组装代码瘦身），二期能力在文末单列不阻塞一期。

**Status:** 一期 Task 1–9 **已完成**（分支 `feat/template-hardening`）。

**Architecture:** Runtime/mapper 只产出 `protocol.OutboundFragment`；`RunLifecycle` 用 `build_event`（稳定九类）或 `build_extension_event`（合法 `x.*`）套信封并唯一编号。扩展事件默认经图 State 的 `OUTBOUND_EXTENSIONS_KEY`，由 runtime 在 `astream_events` 结束后用 `compiled.aget_state(config)` 读取并 yield；域不得持有 `EventSink`。`event_hook` 为规格中的同级高级选项，一期不实现。

**Tech Stack:** Python 3.12+、Pydantic v2、LangGraph、FastAPI、pytest、import-linter。

**Spec:** `docs/superpowers/specs/2026-07-24-template-hardening-optimization-design.md`

## Global Constraints

- 一期**会改** `packages/core`；硬化后新业务插件零改 core；core 禁止出现 `demo_tools` / 业务节点名硬编码（如 `echo_node`）
- `OutboundFragment` 与 **`OUTBOUND_EXTENSIONS_KEY`** 属于 **`protocol/`**，禁止放在 `adapters/` 或 `application/`；域与 runtime **禁止**散落字面量 `"outbound_extensions"`
- 扩展读取默认：**`compiled.aget_state(config)`**，禁止用 `on_chain_end` 猜节点 output；`event_hook` 为一期**不实现**的同级高级选项（规格允许，计划默认不做）
- **域不得持有 `EventSink`**（扩展只写 State / 未来 hook，不直推 SSE）
- `GraphRuntime.astream` 的 Protocol 返回类型为 `AsyncIterator[OutboundFragment]`（与实现一致）
- Builder **Option B**：`build_event` 仅稳定九类；`build_extension_event` 仅合法 `x.*`；非法前缀 **禁止 silent drop**
- lifecycle 终端保证与 **chat.py 删除 r-host / 禁止双发 error** 必须在 **同一 Task（Task 6）** 完成；不得拖到 lifespan 瘦身
- **不新增** `ensure_route`；未知 route 靠 lifecycle/`graphs.get` → `UnknownRoute`，路由只映射 HTTP 400
- `demo_tools` **无 LLM**；CI 零外部 API key
- 生产 `app.state` 仅 `run_lifecycle` + `settings`；禁止暴露 locks/cancels/graphs/tools/input_builders
- 唯一 `new` 适配器 = lifespan；`public` 不 new
- Postgres：**`pg_dsn` 优先**；空则 fallback `pg_host/port/database/user/password`；工厂只收最终 DSN 字符串
- 允许 `adapters.* → adapters.*`，且 **import-linter 白名单**约束边；补 code-structure
- 路径写仓库相对全路径；每 Task 测绿再 commit
- 二期（Redis 锁等）不阻塞一期宣布；对外叙事：模板可用 ≠ 多副本生产（单机默认、无分布式锁、无完整 OTel/interrupt）

## Spec 落地顺序 ↔ Task 映射

规格必须先完成 0→4 步与本计划 Task 对应（lifecycle/r-host 为规格一期目标，插在 runtime 与 demo 之间，因 Fragment 产出后必须先改 lifecycle）：

| Spec 步 | 内容 | Plan Task |
|---------|------|-----------|
| 0 | 对齐 `contracts.md` | 1 |
| 1 | Fragment + Option B + mapper/`tool_result` + 最小 step | 2 → 3 → 4 |
| 2 | `langgraph_runtime`：`on_tool_end` + 扩展抽取 + step | 5 |
| （一期目标 6） | cancel `data` + `terminal_sent` + 删 r-host / 禁双发 | **6** |
| 3 | 挂 `demo_tools` | 7 |
| 4 | 瘦 lifespan + `app.state` | 8 |
| 收口 | 文档叙事 / 验收条件 / Web 软 / 决策树软 | 9 |

## File map（一期）

| 路径 | 职责 |
|------|------|
| `packages/core/src/agentbridge_core/protocol/fragments.py` | **新建** `OutboundFragment` + `OUTBOUND_EXTENSIONS_KEY` |
| `packages/core/src/agentbridge_core/protocol/events.py` | `build_event` 收紧；新增 `build_extension_event` + `EXTENSION_TYPE_RE` |
| `packages/core/src/agentbridge_core/protocol/__init__.py` | 按需导出 |
| `packages/core/src/agentbridge_core/adapters/event_mapper.py` | 返回 Fragment；加 `map_tool_result` |
| `packages/core/src/agentbridge_core/adapters/langgraph_runtime.py` | `on_tool_end` / 最小 step / **`aget_state` 读扩展** |
| `packages/core/src/agentbridge_core/ports/graph_runtime.py` | Protocol 返回类型改为 `AsyncIterator[OutboundFragment]` |
| `packages/core/src/agentbridge_core/application/run_lifecycle.py` | Fragment→信封；cancel data；terminal_sent |
| `packages/core/src/agentbridge_core/ports/event_sink.py` | 仍 emit `dict`（完整信封） |
| `apps/api/routes/chat.py` | **与 Task 6 同改**：删 r-host、禁双发 error |
| `docs/contracts.md` | 对齐稳定九类 + `x.*`；cancel data 样例保留 |
| `docs/superpowers/specs/2026-07-23-code-structure.md` | adapters 同层允许 |
| `.importlinter` | adapters 内部边白名单 |
| `apps/api/domains/demo_tools/*` | 无 LLM 样板域 |
| `apps/api/domains/bootstrap.py` | 注册 echo + demo_tools |
| `apps/api/lifespan.py` / `config/settings.py` | Fake 迁出；`pg_dsn`；app.state；hooks |
| `apps/api/testing/fake_runtime.py` | Fake 迁出落点 |
| `scripts/import_scan_core.py`（或新测） | 禁 core 含 `demo_tools` / `echo_node` |
| `README.md` / `docs/deploy.md` / `docs/add-a-domain.md` | 叙事 + 决策树（软） |

---

### Task 1: contracts.md 对齐

**Files:**
- Modify: `docs/contracts.md`

- [x] **Step 1: 改 §2 域扩展表述**

删除「type 可为自定义字符串；核心原样透传」。改为：

- 稳定九类列表（与现 `EVENT_TYPES` 一致：`start` / `text_delta` / `tool_call` / `tool_result` / `step_update` / `done` / `error` / `cancel_requested` / `cancelled`）
- 扩展 type 必须匹配 `` `^x\.[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$` ``（禁 `..` / 尾 `.`）
- 非法扩展 type 不得出站；由应用层 `build_extension_event` 拒绝

确认 `cancel_requested` / `cancelled` 样例 `data` 含 `thread_id`、`run_id`（已有则保留）。确认 `tool_result.data` 字段为 `name` / `ok` / `tool_call_id` / `summary`。

- [x] **Step 2: Commit**

```bash
git add docs/contracts.md
git commit -m "docs(contracts): stable event types plus x.* extension rules"
```

---

### Task 2: protocol.OutboundFragment + OUTBOUND_EXTENSIONS_KEY

**Files:**
- Create: `packages/core/src/agentbridge_core/protocol/fragments.py`
- Modify: `packages/core/src/agentbridge_core/protocol/__init__.py`（可选 re-export）
- Create: `packages/core/tests/protocol/test_fragments.py`

**Interfaces:**
- Produces: `OutboundFragment`、`OUTBOUND_EXTENSIONS_KEY`
- Consumed later by: `event_mapper`、`LangGraphRuntime`、`RunLifecycle`、`demo_tools` State

**模型定义（必须按此实现，放在 protocol 层）：**

```python
# packages/core/src/agentbridge_core/protocol/fragments.py
"""Semantic outbound payload before RunLifecycle assigns envelope fields."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

OUTBOUND_EXTENSIONS_KEY = "outbound_extensions"


class OutboundFragment(BaseModel):
    """Protocol-layer fragment: type + data only (no run_id/sequence/event_id).

    Adapters and domain state may produce this model. Application layer
    (RunLifecycle) converts it to a contracts envelope via build_event or
    build_extension_event. Must live under protocol/, not adapters/application.
    """

    model_config = ConfigDict(extra="forbid")

    type: str
    data: dict[str, Any] = Field(default_factory=dict)
    step: str | None = None
    status: str | None = None
```

- [x] **Step 1: 写失败测试**

```python
# packages/core/tests/protocol/test_fragments.py
from agentbridge_core.protocol.fragments import (
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
```

- [x] **Step 2: 跑测确认失败**

Run: `python -m pytest packages/core/tests/protocol/test_fragments.py -v`  
Expected: FAIL（模块不存在）

- [x] **Step 3: 实现 `fragments.py`（上文模型原文落地）**

- [x] **Step 4: 跑测通过**

Run: `python -m pytest packages/core/tests/protocol/test_fragments.py -v`  
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add packages/core/src/agentbridge_core/protocol packages/core/tests/protocol/test_fragments.py
git commit -m "feat(core): add OutboundFragment and OUTBOUND_EXTENSIONS_KEY"
```

---

### Task 3: Option B builders + extension regex

**Files:**
- Modify: `packages/core/src/agentbridge_core/protocol/events.py`
- Modify: `packages/core/tests/protocol/test_sse.py`

**Interfaces:**
- `EVENT_TYPES: frozenset[str]`（不变九类）
- `EXTENSION_TYPE_RE: re.Pattern[str]` = `re.compile(r"^x\.[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")`
- `build_event(...)` — **仅** `type in EVENT_TYPES`，否则 `ValueError`
- `build_extension_event(type, *, run_id, sequence, trace_id, data=None, step=None, status=None) -> dict` — 仅当 `EXTENSION_TYPE_RE.fullmatch(type)`，否则 `ValueError`（禁止 silent drop）
- 两者返回完整信封 dict（含 timestamp / event_id）

- [x] **Step 1: 写失败测试**

```python
import pytest
from agentbridge_core.protocol.events import build_event, build_extension_event


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
```

（保留既有 `test_build_start_event_shape` 等。）

- [x] **Step 2: 实现 → pytest `packages/core/tests/protocol/` 全绿**

- [x] **Step 3: Commit**

```bash
git commit -m "feat(core): Option B build_event vs build_extension_event"
```

---

### Task 4: event_mapper → OutboundFragment + map_tool_result

**Files:**
- Modify: `packages/core/src/agentbridge_core/adapters/event_mapper.py`
- Modify: `packages/core/tests/adapters/test_event_mapper.py`

**Interfaces:**
- `map_text_delta(content: str) -> OutboundFragment`（**不再**调用 `build_event`，**不接收** `run_id`/`sequence`/`trace_id`）
- `map_tool_call(name: str, args: dict, tool_call_id: str) -> OutboundFragment`
- `map_tool_result(name: str, *, ok: bool, tool_call_id: str, summary: str) -> OutboundFragment`
- `map_step_update(step: str, status: str) -> OutboundFragment`

签名示例：

```python
def map_text_delta(content: str) -> OutboundFragment:
    return OutboundFragment(type="text_delta", data={"content": content})


def map_tool_result(
    name: str, *, ok: bool, tool_call_id: str, summary: str
) -> OutboundFragment:
    return OutboundFragment(
        type="tool_result",
        data={"name": name, "ok": ok, "tool_call_id": tool_call_id, "summary": summary},
    )
```

- [x] **Step 1: 更新/新增测试断言返回 `OutboundFragment` 且无 sequence 字段；`map_tool_result` 字段对齐 contracts**

- [x] **Step 2: 实现 → 测绿 → Commit**

```bash
git commit -m "feat(core): mappers return OutboundFragment; add map_tool_result"
```

---

### Task 5: LangGraphRuntime 防腐闭合 + Port 签名

**Files:**
- Modify: `packages/core/src/agentbridge_core/ports/graph_runtime.py`
- Modify: `packages/core/src/agentbridge_core/adapters/langgraph_runtime.py`
- Create/Modify: `packages/core/tests/adapters/test_langgraph_runtime.py`（或扩展现有测）

**Interfaces:**
- `GraphRuntime.astream(...) -> AsyncIterator[OutboundFragment]`（Protocol 与实现一致；**不再** `AsyncIterator[dict]`）
- 扩展键：从 `agentbridge_core.protocol.fragments` import `OUTBOUND_EXTENSIONS_KEY`

**行为（对齐规格 §3.5 / §3.6）:**
1. `async for` yield **`OutboundFragment`**（不是完整 event dict）
2. `on_tool_end` → `map_tool_result`（`name`/`ok`/`tool_call_id`/`summary`）
3. 最小 `on_chain_start` → `map_step_update(step=name, status="running")`；对应 end 可发 `status="done"`（**demo_tools 验收不强制看到 step**）
4. **扩展读取（写死，用 `aget_state`）：**  
   - 主循环跑完 `astream_events` 后：  
     `snapshot = await compiled.aget_state(config)`（`config` 与跑图相同，含 `thread_id`）  
     `raw = (snapshot.values or {}).get(OUTBOUND_EXTENSIONS_KEY) or []`  
   - 对 `raw` 每一项 yield `OutboundFragment(type=item["type"], data=item.get("data") or {})`  
   - **禁止**从 `on_chain_end` 解析节点 output 猜扩展列表  
   - **此处不跑 `EXTENSION_TYPE_RE`**（交给 lifecycle）  
   - 一期**不实现** `event_hook`
5. 去掉业务节点名硬编码；通用 `_text_from_chain_output` 可保留

- [x] **Step 1: 单测 `aget_state` 扩展读取**（mock `compiled.aget_state` 返回含 `OUTBOUND_EXTENSIONS_KEY` 的 values；断言 yield 对应 Fragment；断言**未**依赖 `on_chain_end` 猜扩展）

- [x] **Step 2: 更新 Port + 实现 → 测绿 → Commit**

```bash
git commit -m "feat(core): runtime emits fragments via aget_state extensions"
```

---

### Task 6: RunLifecycle 终端保证 + chat 删除 r-host（同一切片）

**Files:**
- Modify: `packages/core/src/agentbridge_core/application/run_lifecycle.py`
- Modify: `packages/core/tests/application/test_run_lifecycle.py`
- Modify: `packages/core/tests/conftest.py`（FakeRuntime yield `OutboundFragment`）
- Modify: `apps/api/routes/chat.py`（**本 Task 必须改完**，勿留到 Task 8）
- Modify: `apps/api/tests/test_chat_stream.py`（若依赖旁路行为则更新）

**行为（lifecycle，对齐规格 §3.3 / §3.4 / §3.7）:**
1. `async for frag in runtime.astream(...)`：  
   - `frag.type in EVENT_TYPES` → `build_event(..., data=frag.data, step=frag.step, status=frag.status)`  
   - `EXTENSION_TYPE_RE.fullmatch(frag.type)` → `build_extension_event(...)`  
   - 否则 → 发稳定 `error` 并置 `terminal_sent`（**不要**静默丢掉非法 type）  
2. 统一递增 `sequence`，再 `sink.emit(dict)`（lifecycle 是唯一编号点）  
3. `cancel_requested` / `cancelled`：`data={"thread_id": thread_id, "run_id": run_id}`  
4. `terminal_sent`：`try_acquire` 成功后，`sink.close()` 前必须已发 `done` **或** cancel 对 **或** `error` 之一；`ThreadBusy` 仍只抛异常、不发 SSE  
5. Fake/Slow/Boom runtime 改为 yield `OutboundFragment`

**行为（chat.py，与上同步）:**
1. **删除** `run_id="r-host"` / `sequence=0` 的假 error 帧  
2. `_run` 的 `except Exception`：**不得**在 lifecycle 已通过 sink 发出 `error` 后再往 queue 塞第二帧 error；`ThreadBusy`/`UnknownRoute` 开流前映射保持；其余异常若 sink 已关闭则只结束生成器  
3. **不新增** `ensure_route`  
4. 集成/单测确认：**一条失败流最多一帧 `type=error`**；全文无 `r-host`

- [x] **Step 1: core 测** — cancel `data` 含 `thread_id`+`run_id`；非法扩展 type（如 `x.`）→ 稳定 `error`；`terminal_sent` 路径；既有 echo/busy/cancel 绿  

- [x] **Step 2: 改 chat.py + api 测** — 无 r-host；无双 error  

- [x] **Step 3: `python -m pytest packages/core/tests -v` 且 `cd apps/api && python -m pytest tests -v`**

- [x] **Step 4: Commit**

```bash
git commit -m "feat(core,api): lifecycle envelopes + remove chat r-host duplicate errors"
```

---

### Task 7: demo_tools 域（无 LLM）

**Files:**
- Create: `apps/api/domains/demo_tools/{state,tools,graph,bootstrap}.py` + `README.md`
- Modify: `apps/api/domains/bootstrap.py`
- Create: `apps/api/tests/test_demo_tools_stream.py`

**行为（对齐规格 §4）:**
- Tool（如 `add`）真绑定；图 **无** ChatModel / **无** `LLM_API_KEY` 依赖
- State 用 **`OUTBOUND_EXTENSIONS_KEY`** 写入 list；结束前 append `{"type": "x.demo_tools.finished", "data": {...}}`
- **域不得** import / 持有 `EventSink`
- 集成测验收流：`start` → `tool_call` → `tool_result` → ≥1×`x.demo_tools.*` → `done`（`text_delta`/`step_update` **不强制**）
- 图可用 ToolNode + 预置 `tool_calls` 的 Fake AIMessage（无真实 LLM）；细节见域 README
- `register_all` 注册 echo + demo_tools

- [x] **Step 1: 实现域 + bootstrap 注册**

- [x] **Step 2: 集成测绿（`AGENTBRIDGE_FAKE_RUNTIME=0`）**

- [x] **Step 3: 确认 `rg demo_tools packages/core` 无匹配**

- [x] **Step 4: Commit**

```bash
git commit -m "feat(api): add demo_tools domain with tool SSE and x.* extension"
```

---

### Task 8: 宿主瘦身 + DSN + hooks + adapters 验收条件

**Files:**
- Create: `apps/api/testing/fake_runtime.py`
- Modify: `packages/core/src/agentbridge_core/application/run_lifecycle.py`（测试钩子，见下）
- Modify: `apps/api/lifespan.py`、`config/settings.py`、`main.py`（如需）
- Modify: `apps/api/tests/test_chat_cancel.py`（及任何 `app.state.cancels`/`locks` 直访）
- Modify: `docs/superpowers/specs/2026-07-23-code-structure.md`（写明 adapters→adapters 允许）
- Modify: `.importlinter`（adapters 白名单：如仅 `langgraph_runtime` → `event_mapper`）
- Modify: `.env.example`、`docs/deploy.md`

**行为（对齐规格 §5 / §5.1）:**
- Fake 迁出 lifespan；仅测试/env 开关 import
- `app.state` **生产允许**仅 `run_lifecycle` + `settings`；**禁止暴露** locks/cancels/graphs/tools/input_builders
- Settings：新增 **`pg_dsn`**（优先）；空则用五字段拼接；工厂只收最终 DSN 字符串
- `hooks_backend=noop|logging`
- **确认** chat.py 已无 r-host（Task 6）；本 Task 不重开旁路、**不**新增 `ensure_route`
- 唯一 `new` 适配器仍在 lifespan；`public` 不 new
- import-linter + code-structure 同步
- **回归**：echo / 409 busy / cancel / auth 相关 api 测保持绿

**测试迁移（写死，避免实施时临时设计）：**

1. **Cancel 预注册** — 当前 `test_chat_cancel.py` 直接：

```python
await client.app.state.cancels.register("t-cancel", "r1", token)
```

Task 8 后 `app.state.cancels` 不再存在。给 `RunLifecycle` 加**仅测试用**钩子（与既有 `replace_runtime` 同风格），经 `app.state.run_lifecycle` 调用，**不**把 registry 挂回 `app.state`：

```python
# packages/core/src/agentbridge_core/application/run_lifecycle.py
async def _test_register_cancel(
    self,
    thread_id: str,
    run_id: str,
    token: asyncio.Event | None = None,
) -> asyncio.Event:
    """Test-only: pre-register a cancel token without starting a stream."""
    token = token or asyncio.Event()
    await self._cancels.register(thread_id, run_id, token)
    return token
```

```python
# apps/api/tests/test_chat_cancel.py
def test_cancel_200_when_registered(client):
    async def _reg():
        await client.app.state.run_lifecycle._test_register_cancel("t-cancel", "r1")

    anyio.run(_reg)
    r = client.post("/chat/cancel", json={"thread_id": "t-cancel", "run_id": "r1"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
```

2. **graphs/tools 注册** — `conftest.py` / `test_auth_optional.py` 现有 `app.state.graphs.register("echo", ...)`。优先：**依赖 lifespan 里 `register_all` 已注册的真实 echo**（fake runtime 下仍走 lifecycle→runtime，不依赖 graphs 返回值形状则够用）；删掉对 `app.state.graphs`/`tools` 的直访。若某测必须换 builder：再给 `RunLifecycle` 加对称钩子 `_test_register_graph(route, builder)` / `_test_register_tools(route, tools)`，同样不暴露 `app.state.graphs`。

3. **locks** — 勿把 `locks` 挂回 `app.state`；409 busy 用双开流测公开行为。流内 cancel（`test_cancel_during_stream_emits_cancelled`）已用 `replace_runtime`，一般无需改注册路径。

- [x] **Step 1: 加 `_test_register_cancel` + 改 `test_chat_cancel.py` + lifespan/`app.state` 收敛 + Fake/DSN/hooks**

- [x] **Step 2: `cd apps/api && python -m pytest tests -v` 全绿（含 cancel / 409 / echo / auth）**

- [x] **Step 3: 根目录 `lint-imports` + import/业务插件名扫描**

- [x] **Step 4: Commit**

```bash
git commit -m "refactor(api): slim lifespan app.state; DSN and hooks settings"
```

---

### Task 9: 文档与验收条件收口（一期）

**Files:**
- Modify: `README.md`、`docs/add-a-domain.md`、`docs/parity-with-product.md`、`docs/deploy.md`（若叙事未写全）
- Modify: `scripts/import_scan_core.py` 或新增 `scripts/scan_core_no_domain_names.py`
- Modify: `.github/workflows/ci.yml`（如需跑新扫描）
- Optional: `apps/web/src/features/contracts/ContractsPage.tsx`、`DebugPage.tsx`（软要求）

- [x] **Step 1: 文档（硬）** — Fragment / Option B / `OUTBOUND_EXTENSIONS_KEY`+`aget_state` / demo_tools 无 LLM / **「模板可用 ≠ 多副本」**（单机默认、无分布式锁、无完整 OTel/interrupt）/ **域不得持 EventSink** / **state 与 event_hook 同级**（hook 一期未实现，复杂域可选）/ §1.1「零改 core」措辞

- [x] **Step 2: 验收条件（硬）** — core 禁 `demo_tools`、`echo_node`；确认 Task 8 的 import-linter adapters 白名单已挂且 CI 跑

- [x] **Step 3（可选·软）: Web** — Contracts 注明 `demo_tools`/`x.*`；未知 `x.*` 可折叠（不进硬验收红线）

- [x] **Step 4（可选·软）: `add-a-domain.md`「何时必须改 core」决策树** — 薄版即可，不挡硬验收

- [x] **Step 5: CI 绿** — core / api **分目录** pytest + lint-imports + 扫描

- [x] **Step 6: Commit**

```bash
git commit -m "docs: harden runbooks; ci: ban domain names in core"
```

---

## 二期（后置 Tasks，不阻塞一期）

| Task | 内容 |
|------|------|
| P2-1 | Redis `ThreadLock` + `RunCancelRegistry`；`lock_backend` 切换 |
| P2-2 | `/ready`；deploy 多副本前提 |
| P2-3 | JWKS TTL；入站 `trace_id`；可配置 hooks |
| P2-4（体验） | 可选 `demo_llm` 域（需 key）；不挡一期 |
| P2-doc | PKCE 闭环（规格可选） |

---

## Plan self-review（对照规格验收清单）

| Spec §8 / 要求 | Task | 备注 |
|----------------|------|------|
| contracts：稳定九类 + `x.*`；无任意透传 | 1 | |
| `build_event` / `build_extension_event`；非法失败测 | 3 | |
| OutboundFragment ∈ protocol；lifecycle 唯一编号 | 2 + 6 | |
| `OUTBOUND_EXTENSIONS_KEY` 常量 | 2 | |
| `map_tool_result` + `on_tool_end` | 4 + 5 | |
| 最小 `step_update` 映射（demo 验收不强制） | 5 | |
| 扩展：`aget_state` 读；禁止 on_chain_end 猜 | 5 | |
| cancel `data` 含 thread_id+run_id | 6 | |
| `terminal_sent` | 6 | |
| 无 r-host；无双发 error | 6 | |
| 不新增 `ensure_route` | 6 + 8 | |
| 域不持 EventSink | 7 + Global | |
| `demo_tools` 无 LLM；流验收 | 7 | |
| lifespan 无 Fake；app.state 白名单 | 8 | |
| `pg_dsn` 优先 + 五字段 fallback | 8 | |
| hooks_backend | 8 | |
| adapters→adapters + import-linter 白名单 | 8 | |
| echo/409/cancel/auth 回归 | 8 | 含 `_test_register_cancel` 迁移 |
| core 无 `demo_tools`/`echo_node`；验收条件 | 9 | |
| 对外叙事：模板可用 ≠ 多副本 | 9 | |
| Web 软 / 决策树软 / demo_llm 后续 | 9 软 / 二期 | |
| Redis /ready / JWKS | 二期 | |

**相对上一版 plan 的对齐修订：**

1. Architecture / Global 与规格用词对齐：`aget_state`、`OUTBOUND_EXTENSIONS_KEY`、`pg_dsn`、域禁 EventSink、禁 ensure_route  
2. 增加 Spec 落地顺序 ↔ Task 映射表（含 Task 6 插入理由）  
3. Task 5 Step 1 从「累积逻辑」改为「`aget_state` 读取」测  
4. Task 6 补 step/status 传入 builder、terminal/Busy 语义、ensure_route  
5. Task 8 字段名 `pg_dsn`（非 `postgres_dsn`）；显式回归 echo/409/cancel/auth  
6. Task 9 文档硬项含 hook 同级叙事与 §1.1 措辞  
7. Self-review 覆盖规格 §8 全表  
8. Task 3：`rejects_bad` 扩到 9 个边界 case（含 `""` / `x.123b.c` / `x..c` / `x.a.b@d`）  
9. Task 8：钉死 `_test_register_cancel` + graphs 依赖 `register_all` / 对称钩子，避免实施时临时设计  
