# Template Hardening + Production Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按修订规格完成一期模板硬化（契约单源、OutboundFragment、Option B builders、tool_result、demo_tools、组装根瘦身），二期能力在文末单列不阻塞一期。

**Architecture:** Runtime/mapper 只产出 `protocol.OutboundFragment`；`RunLifecycle` 用 `build_event`（稳定九类）或 `build_extension_event`（`x.*`）套信封并唯一编号；扩展事件经图状态 `outbound_extensions` 抽出，域不持有 `EventSink`。

**Tech Stack:** Python 3.12+、Pydantic v2、LangGraph、FastAPI、pytest、import-linter。

**Spec:** `docs/superpowers/specs/2026-07-24-template-hardening-optimization-design.md`

## Global Constraints

- 一期**会改** `packages/core`；硬化后新域零改 core；core 禁止出现 `demo_tools` / 业务节点名硬编码
- `OutboundFragment` 与 **`OUTBOUND_EXTENSIONS_KEY`** 属于 **`protocol/`**，禁止放在 `adapters/` 或 `application/`
- 扩展读取默认：**`compiled.aget_state(config)`**，禁止用 `on_chain_end` 猜节点 output；`event_hook` 为一期**不实现**的同级高级选项（规格允许，计划默认不做）
- `GraphRuntime.astream` 的 Protocol 返回类型为 `AsyncIterator[OutboundFragment]`（与实现一致）
- Builder **Option B**：`build_event` 仅稳定九类；`build_extension_event` 仅合法 `x.*`
- lifecycle 终端保证与 **chat.py 删除 r-host / 禁止双发 error** 必须在 **同一 Task** 完成
- `demo_tools` **无 LLM**；CI 零外部 API key
- 生产 `app.state` 仅 `run_lifecycle` + `settings`；禁止暴露 locks/cancels/graphs/tools/input_builders
- 允许 `adapters.* → adapters.*`，且 **import-linter 白名单**约束边；补 code-structure
- 路径写仓库相对全路径；每 Task 测绿再 commit
- 二期（Redis 锁等）不阻塞一期宣布；对外叙事：模板可用 ≠ 多副本生产

## File map（一期）

| 路径 | 职责 |
|------|------|
| `packages/core/src/agent_base_core/protocol/fragments.py` | **新建** `OutboundFragment` + `OUTBOUND_EXTENSIONS_KEY` |
| `packages/core/src/agent_base_core/protocol/events.py` | `build_event` 收紧；新增 `build_extension_event` + `EXTENSION_TYPE_RE` |
| `packages/core/src/agent_base_core/protocol/__init__.py` | 按需导出 |
| `packages/core/src/agent_base_core/adapters/event_mapper.py` | 返回 Fragment；加 `map_tool_result` |
| `packages/core/src/agent_base_core/adapters/langgraph_runtime.py` | `on_tool_end` / step / **`aget_state` 读扩展** |
| `packages/core/src/agent_base_core/ports/graph_runtime.py` | Protocol 返回类型改为 `AsyncIterator[OutboundFragment]` |
| `packages/core/src/agent_base_core/application/run_lifecycle.py` | Fragment→信封；cancel data；terminal_sent |
| `packages/core/src/agent_base_core/ports/event_sink.py` | 仍 emit `dict`（完整信封） |
| `apps/api/routes/chat.py` | **与 Task 6 同改**：删 r-host、禁双发 error |
| `docs/contracts.md` | 对齐稳定九类 + `x.*`；cancel data |
| `docs/superpowers/specs/2026-07-23-code-structure.md` | adapters 同层允许 |
| `.importlinter` | adapters 内部边白名单 |
| `apps/api/domains/demo_tools/*` | 无 LLM 样板域 |
| `apps/api/domains/bootstrap.py` | 注册 echo + demo_tools |
| `apps/api/lifespan.py` / `config/settings.py` | Fake 迁出；DSN；app.state；hooks |
| `apps/api/testing/fake_runtime.py` | Fake 迁出落点 |
| `scripts/import_scan_core.py`（或新测） | 禁 core 含 `demo_tools` / `echo_node` |

---

### Task 1: contracts.md 对齐

**Files:**
- Modify: `docs/contracts.md`

- [ ] **Step 1: 改 §2 域扩展表述**

删除「type 可为自定义字符串；核心原样透传」。改为：

- 稳定九类列表（与现 EVENT_TYPES 一致）
- 扩展 type 必须匹配 `` `^x\.[a-z][a-z0-9_]*\.[a-z0-9_.]+$` ``
- 非法扩展 type 不得出站

确认 `cancel_requested` / `cancelled` 样例 `data` 含 `thread_id`、`run_id`（已有则保留）。

- [ ] **Step 2: Commit**

```bash
git add docs/contracts.md
git commit -m "docs(contracts): stable event types plus x.* extension rules"
```

---

### Task 2: protocol.OutboundFragment（Pydantic）

**Files:**
- Create: `packages/core/src/agent_base_core/protocol/fragments.py`
- Modify: `packages/core/src/agent_base_core/protocol/__init__.py`（可选 re-export）
- Create: `packages/core/tests/protocol/test_fragments.py`

**Interfaces:**
- Produces: `OutboundFragment`（见下方完整定义）
- Consumed later by: `event_mapper`, `LangGraphRuntime`, `RunLifecycle`

**模型定义（必须按此实现，放在 protocol 层）：**

```python
# packages/core/src/agent_base_core/protocol/fragments.py
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

- [ ] **Step 1: 写失败测试**

```python
# packages/core/tests/protocol/test_fragments.py
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
```

- [ ] **Step 2: 跑测确认失败**

Run: `python -m pytest packages/core/tests/protocol/test_fragments.py -v`  
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `fragments.py`（上文模型原文落地）**

- [ ] **Step 4: 跑测通过**

Run: `python -m pytest packages/core/tests/protocol/test_fragments.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/agent_base_core/protocol packages/core/tests/protocol/test_fragments.py
git commit -m "feat(core): add protocol.OutboundFragment Pydantic model"
```

---

### Task 3: Option B builders + extension regex

**Files:**
- Modify: `packages/core/src/agent_base_core/protocol/events.py`
- Modify: `packages/core/tests/protocol/test_sse.py`

**Interfaces:**
- `EVENT_TYPES: frozenset[str]`（不变九类）
- `EXTENSION_TYPE_RE: re.Pattern[str]` = `re.compile(r"^x\.[a-z][a-z0-9_]*\.[a-z0-9_.]+$")`
- `build_event(...)` — **仅** `type in EVENT_TYPES`，否则 `ValueError`
- `build_extension_event(type, *, run_id, sequence, trace_id, data=None, step=None, status=None) -> dict` — 仅当 `EXTENSION_TYPE_RE.fullmatch(type)`，否则 `ValueError`
- 两者返回完整信封 dict（含 timestamp / event_id）

- [ ] **Step 1: 写失败测试**

```python
import pytest
from agent_base_core.protocol.events import build_event, build_extension_event


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


@pytest.mark.parametrize("bad", ["X.UPPER.x", "x.", "x.A.b", "custom", "x.demo"])
def test_build_extension_event_rejects_bad(bad):
    with pytest.raises(ValueError):
        build_extension_event(bad, run_id="r1", sequence=1, trace_id="t1")
```

（保留既有 `test_build_start_event_shape` 等。）

- [ ] **Step 2: 实现 → pytest `packages/core/tests/protocol/` 全绿**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(core): Option B build_event vs build_extension_event"
```

---

### Task 4: event_mapper → OutboundFragment + map_tool_result

**Files:**
- Modify: `packages/core/src/agent_base_core/adapters/event_mapper.py`
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

- [ ] **Step 1: 更新/新增测试断言返回 `OutboundFragment` 且无 sequence 字段**

- [ ] **Step 2: 实现 → 测绿 → Commit**

```bash
git commit -m "feat(core): mappers return OutboundFragment; add map_tool_result"
```

---

### Task 5: LangGraphRuntime 防腐闭合 + Port 签名

**Files:**
- Modify: `packages/core/src/agent_base_core/ports/graph_runtime.py`
- Modify: `packages/core/src/agent_base_core/adapters/langgraph_runtime.py`
- Create/Modify: `packages/core/tests/adapters/test_langgraph_runtime.py`（或扩展现有测）

**Interfaces:**
- `GraphRuntime.astream(...) -> AsyncIterator[OutboundFragment]`（Protocol 与实现一致；**不再** `AsyncIterator[dict]`）

**行为:**
1. `async for` yield **`OutboundFragment`**（不是完整 event dict）
2. `on_tool_end` → `map_tool_result`
3. 最小 `on_chain_start` → `map_step_update(step=name, status="running")`；对应 end 可发 `status="done"`（保持简单）
4. **`outbound_extensions` 读取策略（写死，用 `aget_state`）：**  
   - 主循环跑完 `astream_events` 后：  
     `snapshot = await compiled.aget_state(config)`（`config` 与跑图相同，含 `thread_id`）  
     `raw = (snapshot.values or {}).get(OUTBOUND_EXTENSIONS_KEY) or []`  
   - 对 `raw` 每一项 yield `OutboundFragment(type=item["type"], data=item.get("data") or {})`  
   - **禁止**从 `on_chain_end` 解析节点 output 猜扩展列表  
   - **此处不跑 `EXTENSION_TYPE_RE`**（交给 lifecycle）  
   - 一期**不实现** `event_hook`（规格中的同级高级选项留到需要复杂域时再开 Task）
5. 去掉业务节点名硬编码；通用 `_text_from_chain_output` 可保留

- [ ] **Step 1: 单测扩展累积逻辑（纯函数或假 event 序列即可）**

- [ ] **Step 2: 更新 Port + 实现 → 测绿 → Commit**

```bash
git commit -m "feat(core): runtime emits fragments including tool_result and extensions"
```

---

### Task 6: RunLifecycle 终端保证 + chat 删除 r-host（同一切片）

**Files:**
- Modify: `packages/core/src/agent_base_core/application/run_lifecycle.py`
- Modify: `packages/core/tests/application/test_run_lifecycle.py`
- Modify: `packages/core/tests/conftest.py`（FakeRuntime yield `OutboundFragment`）
- Modify: `apps/api/routes/chat.py`（**本 Task 必须改完**，勿留到 Task 8）
- Modify: `apps/api/tests/test_chat_stream.py`（若依赖旁路行为则更新）

**行为（lifecycle）:**
1. `async for frag in runtime.astream(...)`：  
   - `frag.type in EVENT_TYPES` → `build_event`  
   - `EXTENSION_TYPE_RE.fullmatch(frag.type)` → `build_extension_event`  
   - 否则 → 发稳定 `error` 并 `terminal_sent`  
2. 统一递增 `sequence`，`sink.emit(dict)`  
3. cancel 事件 `data={"thread_id", "run_id"}`  
4. `terminal_sent`：acquire 成功后 close 前必有 `done` / cancel 对 / `error` 之一  

**行为（chat.py，与上同步）:**
1. **删除** `run_id="r-host"` / `sequence=0` 的假 error 帧  
2. `_run` 的 `except Exception`：**不得**在 lifecycle 已通过 sink 发出 `error` 后再往 queue 塞第二帧 error；ThreadBusy/UnknownRoute 开流前映射保持；其余异常若 sink 已关闭则只结束生成器  
3. 集成/单测确认：**一条失败流最多一帧 `type=error`**

- [ ] **Step 1: core 测** — cancel data；非法 `x.*` → error；terminal  

- [ ] **Step 2: 改 chat.py + api 测** — 无 r-host；无双 error  

- [ ] **Step 3: `python -m pytest packages/core/tests -v` 且 `cd apps/api && python -m pytest tests -v`**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(core,api): lifecycle envelopes + remove chat r-host duplicate errors"
```

---

### Task 7: demo_tools 域（无 LLM）

**Files:**
- Create: `apps/api/domains/demo_tools/{state,tools,graph,bootstrap,README}.py`（README.md）
- Modify: `apps/api/domains/bootstrap.py`
- Modify: `apps/api/tests/test_demo_tools_stream.py`（新建）

**行为:**
- Tool（如 `add`）真绑定；图无 ChatModel
- State 用 `OUTBOUND_EXTENSIONS_KEY` 写入 list；结束前 append `{"type": "x.demo_tools.finished", "data": {...}}`
- 集成测：SSE 含 `tool_call`、`tool_result`、`x.demo_tools.finished`、`done`
- 图可用 ToolNode + 预置 tool_calls 的 Fake AIMessage（无真实 LLM）；细节见域 README

- [ ] **Step 1: 实现域 + bootstrap 注册**

- [ ] **Step 2: 集成测绿（`AGENT_BASE_FAKE_RUNTIME=0`）**

- [ ] **Step 3: 确认 `rg demo_tools packages/core` 无匹配**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(api): add demo_tools domain with tool SSE and x.* extension"
```

---

### Task 8: 宿主瘦身 + DSN + hooks（r-host 已在 Task 6 完成）

**Files:**
- Create: `apps/api/testing/fake_runtime.py`
- Modify: `apps/api/lifespan.py`、`config/settings.py`、`main.py`（如需）
- Modify: `apps/api/tests/*`（去掉 `app.state.locks` 主路径；fixture 调整）
- Modify: `docs/superpowers/specs/2026-07-23-code-structure.md`
- Modify: `.importlinter`（adapters 白名单边）
- Modify: `.env.example`、`docs/deploy.md`

**行为:**
- Fake 迁出；`app.state` 仅 `run_lifecycle`+`settings`
- `postgres_dsn` 优先 + 五字段 fallback；`hooks_backend=noop|logging`
- **确认** chat.py 已无 r-host（Task 6）；本 Task 不重开旁路
- import-linter：例如仅允许 `langgraph_runtime` → `event_mapper`

- [ ] **Step 1: 实现 → `cd apps/api && python -m pytest tests -v`**

- [ ] **Step 2: 根目录 `lint-imports` + import/域名扫描**

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor(api): slim lifespan app.state; DSN and hooks settings"
```

---

### Task 9: 文档与门禁收口（一期）

**Files:**
- Modify: `README.md`、`docs/add-a-domain.md`、`docs/parity-with-product.md`
- Modify: `scripts/import_scan_core.py` 或新增 `scripts/scan_core_no_domain_names.py`
- Modify: `.github/workflows/ci.yml`（如需跑新扫描）
- Optional: `apps/web/src/features/contracts/ContractsPage.tsx`、`DebugPage.tsx`（软要求）

- [ ] **Step 1: 文档** — Fragment / Option B / `OUTBOUND_EXTENSIONS_KEY`+`aget_state` / demo_tools / **「模板可用 ≠ 多副本」** 叙事

- [ ] **Step 2: 门禁** — core 禁 `demo_tools`、`echo_node`；import-linter adapters 白名单已挂

- [ ] **Step 3（可选·软）: Web** — Contracts 注明 `demo_tools`/`x.*`；未知 `x.*` 可折叠

- [ ] **Step 4（可选·后续文档）: `add-a-domain.md`「何时改 core」决策树** — 可本 Task 做薄版，不挡硬验收

- [ ] **Step 5: CI 绿**

- [ ] **Step 6: Commit**

```bash
git commit -m "docs: harden runbooks; ci: ban domain names in core"
```

---

## 二期（后置 Tasks，不阻塞一期）

| Task | 内容 |
|------|------|
| P2-1 | Redis `ThreadLock` + `RunCancelRegistry`；`lock_backend` 切换 |
| P2-2 | `/ready`；deploy 多副本前提 |
| P2-3 | JWKS TTL；入站 `trace_id` |
| P2-4（体验） | 可选 `demo_llm` 域（需 key）；不挡一期 |

---

## Plan self-review

| Spec 要求 | Task |
|-----------|------|
| contracts 对齐 | 1 |
| OutboundFragment + **OUTBOUND_EXTENSIONS_KEY** ∈ protocol/ | **2** |
| Option B builders | 3 |
| tool_result / mapper | 4 |
| Port + runtime **`aget_state`** 读扩展 | **5** |
| lifecycle + **chat 删 r-host / 禁双发** | **6（合并切片）** |
| demo_tools 无 LLM | 7 |
| lifespan / app.state / DSN / **import-linter 白名单** | 8 |
| 叙事 + 门禁 + Web 软 + 决策树软 | 9 |
| 二期 / demo_llm | 文末 |

**三方评审写入 plan 的钉死项：**

1. 扩展读取 = `aget_state` + `OUTBOUND_EXTENSIONS_KEY`（不用 on_chain_end 猜）  
2. Task 6 = lifecycle **和** chat r-host 同一切片  
3. callback = 规格同级高级选项；**本 plan 一期不实现**  
4. adapters→adapters = code-structure + import-linter 白名单  
5. 对外说清：一期模板可用 ≠ 多副本生产
