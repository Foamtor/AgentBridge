# Plan 4: 智能与治理（M5 + M6 + M7）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.  
> **Rev:** r3 — 对齐 v4.1.1；**硬前置含 Plan1 M2b（RunStore）**；HIL 锁键与 Plan1 `storage_key` 一致。

**Goal:** v1.x：M5 Gateway+Context+Prompt；M6 Filter/Mask/Safety/Approval；M7 Retriever+ingest+demo_rag（+可选 Memory）。

**Architecture:** Runtime 经 Gateway 取模型；审批中 RunStore=`awaiting_approval` 且 **释放 ThreadLock(storage_key)**；resume 同 `run_id` 再 acquire；DataFilter 无规则→[]；可逆脱敏 token_map 绑 run；RAG tenant namespace + `x.bridge.citation`。

**Tech Stack:** LangChain models、tiktoken、pgvector（rag extra）、可选 mem0；pytest。

## 依赖与门禁

| 方向 | 内容 |
|------|------|
| **上游硬** | Plan1 **全量（必须含 RunStore / M2b）**；Plan3 **全量（v1.0 基线）** |
| **上游软** | Plan2（真实 DataSource；无则 Filter/RAG 用 Fake） |
| **下游** | Plan5：SDK 审批演示 **硬依赖** 本 Plan T4；多 Agent/admin 不强制等 M7 |
| **本 Plan 内** | T1→T2→T3（M5）→T4→T5→T6（M6）→T7→T8（M7）→T9 |
| **禁止** | 仅完成 Plan1 M2a、无 RunStore 就做 HIL |

## Global Constraints

- 真源：v4.1.1 §4.6–4.9、§5.2
- `LLM_BACKEND=direct|gateway`，默认 `direct`
- HIL：释锁 / 同 run resume / 超时 deny；**release/acquire 使用与 Plan1 相同的 `storage_key`**
- DataFilter 无规则 → `[]`
- extras 不进必装
- 出口治理边界遵守 §4.9

## Produces

| 产物 | 供谁用 |
|------|--------|
| `LLMGateway` + `LLM_BACKEND` | Plan5 域/SDK 间接 |
| Approval API + `awaiting_approval` | Plan5 SDK `resolveApproval` |
| DataFilter / Masker / SafetyHooks | 生产治理 |
| Retriever + `x.bridge.citation` | demo_rag、后续知识 |

## Spec ↔ Task

| 规格 | Task |
|------|------|
| §5.2 Gateway 过渡 | T1–T3 |
| ContextManager + Prompt | T2 |
| §4.6 Approval | T4 |
| DataFilter + Mask + §4.9 Safety | T5–T6 |
| Retriever + citation + Memory | T7–T8 |

---

### Task 1: LLMGateway Port + DirectLLMGateway

**Interfaces:**
```python
class LLMGateway(Protocol):
    async def chat(self, messages: list[Any], *, ctx: RunContext, model: str | None = None) -> Any: ...
    def stream(self, messages: list[Any], *, ctx: RunContext, model: str | None = None) -> AsyncIterator[Any]: ...
```

- [ ] TDD Direct 委托 FakeModel + Commit `feat(core): LLMGateway direct backend`

---

### Task 2: ContextManager（tiktoken）+ File PromptRegistry

- [ ] `build_messages(..., budget_tokens)` 裁剪可测  
- [ ] `render(name, **vars)`  
- [ ] Commit `feat(core): context manager and file prompts`

---

### Task 3: Runtime/图经 Gateway + 设置开关

- [ ] `settings.llm_backend`  
- [ ] `gateway` 模式下域不新增 `ChatOpenAI(` import（lint 或评审清单）  
- [ ] Commit `feat: honor LLM_BACKEND gateway path`

**M5 门禁：** direct 默认绿；gateway 换模型别名不改域文件。

---

### Task 4: ApprovalGate（对齐 §4.6）

**Files:** `ports/approval.py`、`adapters/memory_approval_store.py`、`routes/approvals.py`、`domains/demo_approval_write/`、修改 lifecycle/RunStore/locks

**必须实现的状态机：**

1. 触发 `require_approval`（Policy 或域显式）→ 写 pending approval  
2. append+emit `x.bridge.approval_required`  
3. **`await locks.release(storage_key, run_id)`**（与 Plan1 相同 storage_key，**不是**裸 API thread_id）；RunStore status=`awaiting_approval`  
4. 同 API `thread_id` 新 `start_stream` **不**因旧锁 409（可测）  
5. `POST /approvals/{id}` → 同 `run_id` resume；`try_acquire(storage_key, run_id)`；失败 409  
6. 超时 → deny + `x.bridge.approval_resolved` + 终端 `done`（data 标明 skipped）

**Fake 驱动：** `ApprovalAwareRuntime` yield 一个特殊 fragment 或 lifecycle 钩子 `request_approval`；不必首版 LangGraph interrupt。

- [ ] **Failing test** `test_approval_releases_lock_allows_second_run`  
- [ ] **Failing test** `test_resume_same_run_id`  
- [ ] **Failing test** `test_timeout_denies`  
- [ ] Implement + Commit `feat: approval gate per v4.1 §4.6`

---

### Task 5: DataFilter deny-by-default + RegexDataMasker

```python
def apply(self, rows, ctx) -> list[dict]:
    if not self.rules:
        return []
```

- [ ] mask/unmask 手机号 roundtrip；token_map 存 `ctx.metadata["token_map"]`（run 作用域）  
- [ ] Commit `feat(core): data filter and regex masker`

---

### Task 6: SafetyHooks on emit_text

- [ ] text_delta 命中手机号 → 告警日志；可配置 redact 后再 append/emit  
- [ ] 遵守 §4.9：不替代 Policy/Gateway  
- [ ] Commit `feat: outbound safety hooks`

**M6 门禁：** 释锁/resume/超时三测绿；无规则无数据；脱敏用例绿。

---

### Task 7: Retriever + ingest + demo_rag

- [ ] `similarity_search(tenant_id=...)`；跨租户空  
- [ ] ingest script  
- [ ] emit `x.bridge.citation`（扩展事件合法 type）  
- [ ] Commit `feat: rag retriever and demo_rag`

---

### Task 8: MemoryStore（optional extra）

- [ ] recall `wait_for(..., 2)` 超时 → `[]`  
- [ ] Commit `feat: MemoryStore port with timeout`

---

### Task 9: 回归

- [ ] roadmap M5–M7；pytest（skip 无 extra）  
- [ ] Commit `docs: Plan4 gates`

## 不在本 Plan

多 Agent/SDK/Redis/Eval（Plan5）。
