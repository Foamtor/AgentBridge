# Plan 2: 可查库（M3）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.  
> **Rev:** r3 — 硬前置仅 Plan1 **M2a**；可与 Plan1 M2b 并行；Produces/门禁表。

**Goal:** v0.3：Postgres `DataSource` + 金标域 `demo_readonly`；无 `order:read` 时 tool 不进 list，有权限可查库（强制 SQL `tenant_id`）。

**Architecture:** DataSource 在 lifespan 构造 → `app.state.data_source`；每次请求 `ctx.metadata["data_source"]=...`。Tool 使用 `Annotated[RunnableConfig, InjectedToolArg]`（或项目选定的 LangChain 注入方式）读 `get_run_context(config)`。依赖 Plan1 的 Policy/Pipeline/RunContext。

**Tech Stack:** asyncpg（`apps/api` optional extra `datasource`）、pytest；PG 集成用 env skip。

## Global Constraints

- **硬前置**：Plan1 **M2a 门禁**（T1–T7：RunContext、Policy、Pipeline、guard_tools、chat 接线）
- **软前置**：Plan1 M2b（有则 messages 可联调；无则本 plan 不测投影）
- **禁止**：等 Plan3 才开始本 plan（Plan2 ∥ Plan1-M2b / Plan3 可行）
- 真源：v4.1.1 产品线 C；`docs/database-integration.md`
- application 不 import asyncpg
- **`ENABLE_DATA_SOURCE` 独立于 `USE_MEMORY_CHECKPOINTER`**
- SQL 参数化 + 强制 `tenant_id`
- 禁止 `ctx: RunContext = None`

## 依赖与门禁

| 方向 | 内容 |
|------|------|
| **上游硬** | Plan1 M2a |
| **上游软** | Plan1 M2b |
| **下游** | Plan3 ready 可选探测；Plan4 DataFilter/金标可真实查库（软） |
| **本 Plan 内** | T1→T2→T3→T4→T5 |

## Produces

| 产物 | 供谁用 |
|------|--------|
| `DataSource` Port + Fake/Postgres | Plan4 Filter 演示、Plan3 `/ready` |
| `demo_readonly` + `order:read` | 验收、Eval 可复用 |
| `ctx.metadata["data_source"]` | 域 tool 约定 |

## Already done

- [x] 硬前置 Plan1 M2a（及本仓库已含 M2b）
- [x] **T1–T5 已实现**（分支 `feat/plan2-datasource`）

## Spec ↔ Task

| 要求 | Task |
|------|------|
| DataSource Port | T1 ✅ |
| Postgres adapter | T2 ✅ |
| metadata 注入 | T3 ✅ |
| demo_readonly + order:read | T4 ✅ |
| 文档/路线图 | T5 ✅ |

---

### Task 1: Port + Fake/Noop

**Files:** `ports/data_source.py`、`adapters/noop_data_source.py`、`adapters/fake_data_source.py`、`tests/adapters/test_fake_data_source.py`

**Interfaces:**
```python
class DataSource(Protocol):
    async def query(self, sql: str, *params: Any) -> list[dict[str, Any]]: ...
    async def execute(self, sql: str, *params: Any) -> int: ...
    async def close(self) -> None: ...
```

- [ ] TDD FakeDataSource（seed 表名匹配）+ Commit `feat(core): DataSource port`

---

### Task 2: PostgresDataSource（api）

**Files:**
- `apps/api/adapters/postgres_data_source.py`
- `apps/api/pyproject.toml` — `datasource = ["asyncpg>=0.29,<1"]`
- `apps/api/config/settings.py`：
  - `enable_data_source: bool = False`（`ENABLE_DATA_SOURCE`）
  - `data_source_dsn: str = ""`（空则回退 `_resolve_postgres_dsn`）
- `apps/api/tests/test_postgres_data_source.py` — skipif 无 `AGENT_BASE_TEST_PG_DSN`

**Wiring rule:**
```python
if settings.enable_data_source:
    dsn = settings.data_source_dsn or _resolve_postgres_dsn(settings)
    ds = PostgresDataSource(dsn)
else:
    ds = NoopDataSource()
```

- [ ] TDD（集成可 skip）+ Commit `feat(api): PostgresDataSource`

---

### Task 3: 注入 metadata

**Files:** `lifespan.py`、`routes/chat.py`（或 deps）

```python
ctx.metadata = {**ctx.metadata, "data_source": request.app.state.data_source}
```

- [ ] 单测/集成断言 `get_run_context(config).metadata["data_source"]` 非空（Fake）
- [ ] Commit `feat(api): inject DataSource into RunContext.metadata`

---

### Task 4: 金标域 `demo_readonly`

**Files:**
- `apps/api/domains/demo_readonly/{__init__,state,tools,graph,bootstrap}.py`
- `apps/api/domains/bootstrap.py`
- `apps/api/migrations/002_demo_readonly.sql`
- `apps/api/tests/test_demo_readonly_policy.py`

**SQL migration:**
```sql
CREATE TABLE IF NOT EXISTS demo_orders (
  id int PRIMARY KEY,
  tenant_id text NOT NULL,
  status text NOT NULL
);
```

**Tool（钉死注入方式）：**

```python
# apps/api/domains/demo_readonly/tools.py
from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import InjectedToolArg, tool
from langchain_core.runnables import RunnableConfig

from agent_base_core.protocol.context import get_run_context
from agent_base_core.registry.tool_meta import attach_tool_meta


@tool
async def list_orders(
    status: str,
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> list[dict[str, Any]]:
    """List orders by status for the current tenant."""
    ctx = get_run_context(config)
    ds = ctx.metadata.get("data_source")
    if ds is None:
        return []
    return await ds.query(
        "SELECT id, status FROM demo_orders WHERE status = $1 AND tenant_id = $2",
        status,
        ctx.tenant_id,
    )


list_orders = attach_tool_meta(list_orders, required_permissions=["order:read"])
```

**Graph：** 复制 `demo_tools` 模式（Fake AIMessage → ToolNode → 结束），无真实 LLM；state 可最小化。

**Tests：**
1. Policy：无 `order:read` → filter 后无 `list_orders`；有则可见  
2. FakeDataSource seed + dev admin stream 或直接调 tool 返回行  
3. 断言 SQL 路径使用 `ctx.tenant_id`（Fake 可记录 last_params）

- [ ] Implement + Commit `feat(api): demo_readonly domain with order:read`

---

### Task 5: 文档验收

- [ ] `docs/database-integration.md` 标 M3 已实现  
- [ ] `docs/roadmap.md` M3  
- [ ] `pytest` 全绿  
- [ ] Commit `docs: mark M3 complete`

## 不在本 Plan

DataFilter（Plan4）、MySQL/Mongo。
