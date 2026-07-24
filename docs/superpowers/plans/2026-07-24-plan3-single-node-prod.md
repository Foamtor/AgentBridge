# Plan 3: 单机生产面（M4）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.  
> **Rev:** r3 — 对齐 v4.1.1；硬/软前置写死；v1.0 门禁含 Plan1+2+3。

**Goal:** 交付 M4 单机生产面；与 Plan1–2 一起构成 **v1.0（单机）**。

## 依赖与门禁

| 方向 | 内容 |
|------|------|
| **上游硬** | Plan1 **全量**（Pipeline 供 InputValidator；建议含 M2b 以便 ready 查 event_log） |
| **上游软** | Plan2（`/ready` 在 `enable_data_source` 时探测；未做则跳过该项） |
| **下游** | Plan4 **硬依赖本 Plan 完成** 方可对外称 v1.x（技术上 M5 可偷跑，发布纪律禁止） |
| **本 Plan 内** | T1→T2→T3→T4→T5→T6 |

## Global Constraints

- 真源：v4.1.1 §9、§11 M4；v1.0 = M0–M4
- 限流进程内；不暗示多机
- InputValidator **必做**
- `/ready` 对缺失依赖 **跳过而非失败**（除非该依赖已 enable 却挂了）

## Produces

| 产物 | 供谁用 |
|------|--------|
| `/ready` `/metrics` 限流 OTel InputValidator | 运维、Plan4 之后基线 |
| v1.0 门禁清单勾选结果 | 发版 |

## Spec ↔ Task

| M4 / v1.0 | Task |
|-----------|------|
| 限流 middleware | T1 |
| /metrics | T2 |
| /ready | T3 |
| OTel 基础 | T4 |
| InputValidator | T5 |
| deploy 清单 + v1.0 标注 | T6 |

---

### Task 1: SlidingWindowLimiter + middleware

**Files:** `apps/api/middleware/rate_limit.py`、`tests/test_rate_limit.py`、`settings.rate_limit_per_minute: int = 0`、`main.py`

- [ ] 单测 limiter 第 3 次 False  
- [ ] middleware 429 `code=rate_limited`  
- [ ] Commit `feat(api): in-process rate limit`

---

### Task 2: Metrics + `/metrics`

**Files:**
- `packages/core/.../ports/metrics.py`（Protocol：`inc` / `observe` / `render_prometheus`）
- `apps/api/adapters/prometheus_metrics.py`
- `apps/api/routes/metrics.py`
- lifespan 注入；lifecycle/hooks `inc("agentbridge_runs_total", labels={"route":...})`

- [ ] GET `/metrics` 含指标名  
- [ ] Commit `feat(api): Prometheus /metrics`

---

### Task 3: `/ready`

**Files:** `routes/ready.py`、`tests/test_ready.py`

检查项（存在才查）：checkpointer setup 标志、event_log ping（memory 恒 ok）、data_source（`enable_data_source` 时 `SELECT 1`）。

- [ ] memory 模式 200  
- [ ] Commit `feat(api): /ready`

---

### Task 4: OTel noop + 可选开启

**Files:** `apps/api/observability/tracing.py`、`settings.otel_enabled`

```python
from contextlib import contextmanager

@contextmanager
def start_run_span(run_id: str, route: str, tenant_id: str):
    yield  # noop; real otel when enabled
```

Lifecycle 在 start 后包一层（可选，失败不影响 run）。

- [ ] Commit `feat(api): noop OTel run spans`

---

### Task 5: InputValidator 插件（必做）

**Files:**
- `packages/core/.../ports/input_validator.py`
- `adapters/basic_input_validator.py`
- `application/pipeline.py` — `InputValidatorPlugin(order=10)`
- `apps/api/tests/test_input_validator.py`

```python
class BasicInputValidator:
    def __init__(self, max_len: int = 8000) -> None:
        self.max_len = max_len

    def validate_query(self, query: str) -> str:
        if len(query) > self.max_len:
            raise ValueError("query too long")
        return query.replace("\x00", "")
```

chat：校验失败 → HTTP 400 `{"detail":{"code":"invalid_input","message":"..."}}`（在创建 StreamingResponse 前）。

- [ ] TDD + Commit `feat: input validator pipeline plugin`

---

### Task 6: v1.0 门禁文档

**验收清单（全部勾上才可打 v1.0 tag）：**

- [ ] M0–M3 已按路线图完成（或明确缺口仅文档）  
- [ ] `/health` `/ready` `/metrics`  
- [ ] 限流可测  
- [ ] InputValidator 400  
- [ ] OTel noop 不抛错  
- [ ] `docs/deploy.md` 单机清单与实现一致  
- [ ] README 写明 v1.0=单机、非多机  

```bash
python -m pytest packages/core/tests apps/api/tests -v
```

- [ ] roadmap M4 完成；Commit `docs: M4 done; v1.0 single-node gate`

## 不在本 Plan

Redis（Plan5）、Gateway（Plan4）。
