# P1 Hardening and RAG-Agent Read-Only Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 P1 审批恢复和工单黄金案例的正确性缺陷，并以固定演示租户只读接入现有 RAG-Agent PostgreSQL/pgvector 与 embedding 服务。

**Architecture:** core 只增加通用 LLM 工具绑定、审批 fencing/sequence/expiry Port 和 Lifecycle 终端语义；API adapter 负责 RAG-Agent schema、PostgreSQL、HTTP embedding 和审批 DTO/组装。`work_order_ops` 仅调用 Lifecycle 传入的 guarded tools，自然语言与 `extra.work_order_draft` 最终生成同一不可变审批 payload。

**Tech Stack:** Python 3.12+、FastAPI、LangGraph、LangChain Core、Pydantic v2、asyncpg、httpx、PostgreSQL 16、pgvector 0.8.2、pytest/pytest-asyncio。

## Global Constraints

- 遵守 `AGENTS.md`：application 不 import adapters；domain 不持有 EventSink、不创建 adapter；core 不出现业务名；adapter 只在 composition root 创建；工具列表过滤和调用期 Policy 双检都必须保留。
- 不修改 `D:\WorkSpace\code\project\RAG_Agent` 的源码、配置、schema 或数据。
- RAG-Agent 数据库只允许 read-only transaction；非 `rag-agent-demo` 租户不得建立外部连接。
- 真实 RAG-Agent 当前契约为 PostgreSQL `kb_document/kb_section/kb_chunk`、pgvector `0.8.2`、`vector(512)`、embedding 模型 `BAAI/bge-m3`。
- 不回写既有 `004_approval_execution.sql` 和 `005_work_order_ops.sql`；使用新 migration `006`、`007`。
- 每项实现遵循 TDD：先写失败测试并确认预期失败，再写最小实现。
- Fake/Memory 测试不能替代 PostgreSQL、pgvector、embedding 和跨实例恢复验收。

---

## File Structure

### Core

- Modify: `packages/core/src/agentbridge_core/ports/llm_gateway.py` — 通用工具绑定参数。
- Modify: `packages/core/src/agentbridge_core/adapters/direct_llm_gateway.py` — `bind_tools` 委托。
- Modify: `packages/core/src/agentbridge_core/adapters/alias_llm_gateway.py` — 工具参数透传。
- Modify: `packages/core/src/agentbridge_core/ports/approval.py` — execution token、sequence cursor、过期审批接口。
- Modify: `packages/core/src/agentbridge_core/adapters/memory_approval_store.py` — Memory 参考语义。
- Modify: `packages/core/src/agentbridge_core/application/run_lifecycle.py` — action 恢复、终端投影、脱敏错误、过期扫描。
- Modify: `packages/core/src/agentbridge_core/errors.py` — 稳定的状态冲突与知识后端异常。
- Test: `packages/core/tests/adapters/test_{direct,alias}_llm_gateway.py`
- Test: `packages/core/tests/application/test_approval_{execution,gate}.py`

### API host and adapters

- Create: `apps/api/adapters/rag_agent_pg_retriever.py` — RAG-Agent schema 的只读 Retriever。
- Modify: `apps/api/adapters/knowledge_backend.py` — `rag_agent_pg` 工厂。
- Modify: `apps/api/adapters/knowledge_ingest_factory.py` — 新后端明确不支持 ingest。
- Modify: `apps/api/adapters/postgres_approval_store.py` — fencing、sequence、expiry。
- Modify: `apps/api/config/settings.py` — RAG-Agent 与 expiry interval 配置。
- Modify: `apps/api/lifespan.py` — 组装和可取消过期扫描任务。
- Modify: `apps/api/routes/approvals.py` — 显式安全 DTO。
- Create: `apps/api/migrations/006_approval_hardening.sql`
- Create: `apps/api/migrations/007_work_order_demo_tenant.sql`
- Create: `apps/api/tests/test_rag_agent_pg_retriever.py`
- Create: `apps/api/tests/test_verify_rag_agent_readonly.py`
- Modify: `apps/api/tests/test_{knowledge_backend_settings,postgres_approval_store,approvals_api}.py`

### Domain and acceptance

- Modify: `apps/api/domains/work_order_ops/{state,tools,graph,bootstrap,README}.py`
- Modify: `apps/api/tests/test_work_order_ops.py`
- Create: `scripts/verify_rag_agent_readonly.py`
- Modify: `.env.example`
- Modify: `docs/{contracts,knowledge-base,release-plan,roadmap}.md`
- Modify: `docs/releases/v0.1.0-tech-preview.md`
- Modify: `apps/api/migrations/README.md`

---

### Task 1: Add generic LLM tool binding to the Gateway Port

**Files:**
- Modify: `packages/core/src/agentbridge_core/ports/llm_gateway.py`
- Modify: `packages/core/src/agentbridge_core/adapters/direct_llm_gateway.py`
- Modify: `packages/core/src/agentbridge_core/adapters/alias_llm_gateway.py`
- Test: `packages/core/tests/adapters/test_direct_llm_gateway.py`
- Test: `packages/core/tests/adapters/test_alias_llm_gateway.py`

**Interfaces:**
- Consumes: existing `LLMGateway.chat(messages, *, ctx, model=None)`.
- Produces:

```python
async def chat(
    self,
    messages: list[Any],
    *,
    ctx: RunContext,
    model: str | None = None,
    tools: list[Any] | None = None,
    tool_choice: str | None = None,
) -> Any: ...
```

- Existing calls without `tools` remain byte-for-byte compatible.
- A model without callable `bind_tools` raises `RuntimeError("llm_tool_binding_unsupported")`.

- [ ] **Step 1: Write failing Direct Gateway tool-binding tests**

Append:

```python
class BindableModel:
    def __init__(self) -> None:
        self.bound: tuple[list[object], str | None] | None = None

    def bind_tools(self, tools, *, tool_choice=None):
        self.bound = (list(tools), tool_choice)
        return self

    async def ainvoke(self, messages):
        return {"messages": list(messages), "bound": self.bound}


@pytest.mark.asyncio
async def test_direct_gateway_binds_only_supplied_guarded_tools() -> None:
    model = BindableModel()
    gateway = DirectLLMGateway(model)
    guarded = [object()]
    out = await gateway.chat(
        [{"role": "user", "content": "create"}],
        ctx=RunContext(tenant_id="rag-agent-demo"),
        tools=guarded,
        tool_choice="prepare_work_order_draft",
    )
    assert model.bound == (guarded, "prepare_work_order_draft")
    assert out["bound"] == model.bound


@pytest.mark.asyncio
async def test_direct_gateway_rejects_tools_when_model_cannot_bind() -> None:
    gateway = DirectLLMGateway(FakeChatModel(["unused"]))
    with pytest.raises(RuntimeError, match="llm_tool_binding_unsupported"):
        await gateway.chat([], ctx=RunContext(), tools=[object()])
```

- [ ] **Step 2: Run the Direct tests and verify RED**

Run:

```powershell
python -m pytest packages/core/tests/adapters/test_direct_llm_gateway.py -v
```

Expected: FAIL because `chat()` does not accept `tools`.

- [ ] **Step 3: Implement the Port and Direct adapter**

Before invocation:

```python
backend = self._model
if tools:
    bind_tools = getattr(backend, "bind_tools", None)
    if not callable(bind_tools):
        raise RuntimeError("llm_tool_binding_unsupported")
    kwargs = {"tool_choice": tool_choice} if tool_choice else {}
    backend = bind_tools(list(tools), **kwargs)
ainvoke = getattr(backend, "ainvoke", None)
```

Do not expose a method that accepts unfiltered registry tools; the caller supplies the guarded list.

- [ ] **Step 4: Add Alias Gateway propagation test and implementation**

Define the same local `BindableModel` test double in
`test_alias_llm_gateway.py` (tests must not import one another), then add:

```python
@pytest.mark.asyncio
async def test_alias_gateway_propagates_tool_binding_to_selected_model() -> None:
    selected = BindableModel()
    gateway = AliasLLMGateway(
        {"default": FakeChatModel(["unused"]), "planner": selected}
    )
    tool = object()
    await gateway.chat(
        [],
        ctx=RunContext(),
        model="planner",
        tools=[tool],
        tool_choice="draft",
    )
    assert selected.bound == ([tool], "draft")
```

Pass `tools` and `tool_choice` from `AliasLLMGateway.chat` to the selected `DirectLLMGateway`.

- [ ] **Step 5: Run all Gateway tests**

Run:

```powershell
python -m pytest packages/core/tests/adapters/test_direct_llm_gateway.py packages/core/tests/adapters/test_alias_llm_gateway.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add packages/core/src/agentbridge_core/ports/llm_gateway.py packages/core/src/agentbridge_core/adapters/direct_llm_gateway.py packages/core/src/agentbridge_core/adapters/alias_llm_gateway.py packages/core/tests/adapters/test_direct_llm_gateway.py packages/core/tests/adapters/test_alias_llm_gateway.py
git commit -m "feat: support guarded llm tool binding"
```

### Task 2: Add approval execution fencing, sequence cursors, and expiry persistence

**Files:**
- Modify: `packages/core/src/agentbridge_core/ports/approval.py`
- Modify: `packages/core/src/agentbridge_core/adapters/memory_approval_store.py`
- Modify: `apps/api/adapters/postgres_approval_store.py`
- Create: `apps/api/migrations/006_approval_hardening.sql`
- Test: `packages/core/tests/application/test_approval_execution.py`
- Modify: `apps/api/tests/test_postgres_approval_store.py`

**Interfaces:**
- `claim_execution(...)` returns a record containing a new non-empty `execution_token`.
- `mark_succeeded` and `mark_retryable_failed` require `execution_token: str`.
- `next_sequence(approval_id, *, tenant_id) -> int` atomically increments `last_sequence`.
- `list_expired_pending(*, now, limit=100) -> list[dict[str, Any]]`.
- `mark_execution_denied` accepts only `approved_pending_execution` or `retryable_failed`.

- [ ] **Step 1: Write the stale-worker fencing test**

```python
@pytest.mark.asyncio
async def test_expired_worker_cannot_finish_new_execution_claim() -> None:
    store, approval_id = await _approved_store()
    t0 = datetime(2026, 7, 30, tzinfo=UTC)
    old = await store.claim_execution(
        approval_id, tenant_id="acme", now=t0, lease_seconds=1
    )
    assert old and old["execution_token"]
    assert await store.recover_expired_execution(
        approval_id, tenant_id="acme", now=t0 + timedelta(seconds=2)
    )
    new = await store.claim_execution(
        approval_id,
        tenant_id="acme",
        now=t0 + timedelta(seconds=2),
        lease_seconds=60,
    )
    assert new and new["execution_token"] != old["execution_token"]
    assert await store.mark_succeeded(
        approval_id,
        tenant_id="acme",
        execution_token=old["execution_token"],
        result={"worker": "old"},
    ) is None
    succeeded = await store.mark_succeeded(
        approval_id,
        tenant_id="acme",
        execution_token=new["execution_token"],
        result={"worker": "new"},
    )
    assert succeeded and succeeded["result"] == {"worker": "new"}
```

- [ ] **Step 2: Write sequence and pending-expiry tests**

```python
@pytest.mark.asyncio
async def test_approval_sequence_is_atomic_and_monotonic() -> None:
    store = MemoryApprovalStore()
    approval_id = await store.create(
        {"tenant_id": "acme", "sequence": 7, "last_sequence": 7}
    )
    values = await asyncio.gather(
        *(store.next_sequence(approval_id, tenant_id="acme") for _ in range(4))
    )
    assert sorted(values) == [8, 9, 10, 11]


@pytest.mark.asyncio
async def test_store_lists_only_expired_pending_records() -> None:
    store = MemoryApprovalStore()
    now = datetime(2026, 7, 30, tzinfo=UTC)
    expired = await store.create(
        {
            "tenant_id": "acme",
            "status": "pending",
            "approval_expires_at": now - timedelta(seconds=1),
        }
    )
    await store.create(
        {
            "tenant_id": "acme",
            "status": "pending",
            "approval_expires_at": now + timedelta(seconds=30),
        }
    )
    rows = await store.list_expired_pending(now=now)
    assert [row["approval_id"] for row in rows] == [expired]
```

- [ ] **Step 3: Run Memory tests and verify RED**

Run:

```powershell
python -m pytest packages/core/tests/application/test_approval_execution.py -v
```

Expected: FAIL on missing token/sequence/expiry behavior.

- [ ] **Step 4: Implement Memory semantics and Port signatures**

Use `uuid.uuid4().hex` for each claim token. All changes remain under the existing `asyncio.Lock`. `recover_expired_execution` must set:

```python
raw["status"] = "retryable_failed"
raw["error"] = "execution_lease_expired"
raw["execution_token"] = None
```

`next_sequence` increments and returns the stored integer. `create` initializes `last_sequence` from `record["last_sequence"]` or `record["sequence"]` or zero.

- [ ] **Step 5: Add migration 006**

```sql
ALTER TABLE approval_records
    ADD COLUMN IF NOT EXISTS execution_token TEXT;
ALTER TABLE approval_records
    ADD COLUMN IF NOT EXISTS last_sequence INTEGER NOT NULL DEFAULT 0;
ALTER TABLE approval_records
    ADD COLUMN IF NOT EXISTS approval_expires_at TIMESTAMPTZ;

UPDATE approval_records
SET last_sequence = GREATEST(last_sequence, COALESCE(sequence, 0));

CREATE INDEX IF NOT EXISTS approval_records_pending_expiry_idx
    ON approval_records (approval_expires_at)
    WHERE status = 'pending';
```

- [ ] **Step 6: Implement equivalent PostgreSQL transitions**

Required SQL properties:

```sql
-- claim
UPDATE approval_records
SET status = 'executing',
    execution_token = $5,
    execution_started_at = $3,
    execution_lease_expires_at = $4
WHERE approval_id = $1 AND tenant_id = $2
  AND status IN ('approved_pending_execution', 'retryable_failed')
RETURNING *;

-- finish
UPDATE approval_records
SET status = $4, result = $5::jsonb, error = $6
WHERE approval_id = $1 AND tenant_id = $2
  AND status = 'executing' AND execution_token = $3
RETURNING *;

-- sequence
UPDATE approval_records
SET last_sequence = last_sequence + 1, updated_at = NOW()
WHERE approval_id = $1 AND tenant_id = $2
RETURNING last_sequence;
```

`create` persists `last_sequence` and `approval_expires_at`; recovery clears `execution_token`.

- [ ] **Step 7: Extend PostgreSQL integration tests**

Apply both `004_approval_execution.sql` and `006_approval_hardening.sql`. Repeat the Memory fencing/sequence assertions against two `PostgresApprovalStore` instances. Keep the existing `AGENTBRIDGE_TEST_PG_DSN` skip marker.

- [ ] **Step 8: Run store tests**

Run:

```powershell
python -m pytest packages/core/tests/application/test_approval_execution.py apps/api/tests/test_postgres_approval_store.py -v
```

Expected: Memory PASS; PostgreSQL PASS when DSN is configured, otherwise explicit skip.

- [ ] **Step 9: Commit**

```powershell
git add packages/core/src/agentbridge_core/ports/approval.py packages/core/src/agentbridge_core/adapters/memory_approval_store.py packages/core/tests/application/test_approval_execution.py apps/api/adapters/postgres_approval_store.py apps/api/tests/test_postgres_approval_store.py apps/api/migrations/006_approval_hardening.sql
git commit -m "feat: fence and sequence approval execution"
```

### Task 3: Correct Lifecycle retry, decision, and terminal projection semantics

**Files:**
- Modify: `packages/core/src/agentbridge_core/application/run_lifecycle.py`
- Modify: `packages/core/src/agentbridge_core/errors.py`
- Modify: `packages/core/tests/application/test_approval_gate.py`
- Modify: `packages/core/tests/application/test_approval_execution.py`

**Interfaces:**
- Produces `ApprovalStateConflict` for deny while executing.
- Uses `ApprovalStore.next_sequence` for every post-approval event.
- Passes the current `execution_token` to all finish operations.
- Projects final messages once; retryable failure updates RunStore to `error` without final MessageStore projection.

- [ ] **Step 1: Write failure-then-success sequence regression**

Create a test executor whose first call raises `RuntimeError("database unavailable")` and second call returns one `OutboundFragment`. Start an action approval, approve twice, then assert:

```python
logged = await event_log.list(run_id, tenant_id="acme")
sequences = [event["sequence"] for event in logged]
assert sequences == sorted(sequences)
assert len(sequences) == len(set(sequences))
assert any(event["type"] == "error" for event in logged)
assert any(event["type"] == "x.example.created" for event in logged)
```

The first approval response must have `status == "retryable_failed"`; the second must have `status == "succeeded"`.

- [ ] **Step 2: Write stale-token and mark-result tests**

Use a store double that returns `None` from `mark_succeeded` for the claimed token. Assert no `x.example.created` event is emitted by that worker and the latest store record is returned.

- [ ] **Step 3: Write decision-transition tests**

Create records through `MemoryApprovalStore.create`, transition one to
`retryable_failed` with the current execution token, and leave a second record
in `executing`. Invoke `RunLifecycle.finalize_approval` against each concrete
record:

```python
denied = await lifecycle.finalize_approval(
    retryable_id,
    tenant_id="acme",
    decision="deny",
    actor=approver,
    sink=sink,
)
assert denied["status"] == "denied"

with pytest.raises(ApprovalStateConflict):
    await lifecycle.finalize_approval(
        executing_id,
        tenant_id="acme",
        decision="deny",
        actor=approver,
        sink=sink,
    )
```

Also assert neither path emits a false `work_order_created`.

- [ ] **Step 4: Write Run/Message projection tests**

For action success, deny, timeout and requester-policy denial:

```python
run = await runs.get(run_id, tenant_id="acme")
assert run and run["status"] == "done"
messages = await messages_store.list_messages("acme", thread_id)
assert [m["role"] for m in messages] == ["user", "assistant"]
```

For retryable executor failure:

```python
run = await runs.get(run_id, tenant_id="acme")
assert run and run["status"] == "error"
assert await messages_store.list_messages("acme", thread_id) == []
```

After later success, assert exactly two messages, not four.

- [ ] **Step 5: Run the new tests and verify RED**

Run:

```powershell
python -m pytest packages/core/tests/application/test_approval_gate.py packages/core/tests/application/test_approval_execution.py -v
```

Expected: sequence reuse, stale Run state and incorrect deny semantics fail.

- [ ] **Step 6: Implement shared helpers**

Add private helpers with these responsibilities:

```python
async def _next_approval_sequence(self, approval_id: str, tenant_id: str) -> int:
    ...

async def _project_action_terminal(
    self,
    *,
    rec: dict[str, Any],
    terminal: str,
    result_delivery_error: str | None = None,
) -> None:
    ...
```

`_project_action_terminal` calls `project_turn` only for final success/deny/timeout/policy denial. If `result_delivery_error` is set, upsert it into RunStore after `project_turn`.

- [ ] **Step 7: Implement token-aware execution**

Use `claimed["execution_token"]`. On executor exception call token-aware `mark_retryable_failed`, emit safe `approval_execution_failed`, set RunStore to `error`, and do not project final messages. After executor success:

```python
updated = await store.mark_succeeded(
    approval_id,
    tenant_id=tenant_id,
    execution_token=execution_token,
    result=normalized_result,
)
if updated is None:
    return await store.get(approval_id, tenant_id=tenant_id) or rec
```

Only then emit created/done.

- [ ] **Step 8: Use store-backed sequence allocation**

Replace local `sequence += 1` in the action resume branch with one `await _next_approval_sequence(...)` per emitted event. Do not change the initial streaming loop or legacy no-action approval sequence in this task.

- [ ] **Step 9: Implement explicit decision conflicts and safe errors**

Add:

```python
class ApprovalStateConflict(RuntimeError):
    pass


class KnowledgeBackendUnavailable(RuntimeError):
    pass
```

For `executing + deny`, raise `ApprovalStateConflict`. Broaden `mark_execution_denied` only for approved/retryable states. Replace executor exception text in SSE with `"approved action execution failed"`; retain detailed text only in internal store/log.

Map known dependency/capability failures before the generic lifecycle exception
handler:

```python
if isinstance(exc, KnowledgeBackendUnavailable):
    code, message = "knowledge_backend_unavailable", "knowledge backend unavailable"
elif str(exc) == "llm_tool_binding_unsupported":
    code, message = (
        "llm_tool_binding_unsupported",
        "configured model does not support tool binding",
    )
else:
    code, message = "run_failed", "run failed"
```

Tests assert that raw DSNs, credentials, SQL errors and exception text do not
appear in SSE or API responses.

- [ ] **Step 10: Remove the existing EOF whitespace failure and run tests**

Run:

```powershell
python -m pytest packages/core/tests/application/test_approval_gate.py packages/core/tests/application/test_approval_execution.py -v
git diff --check -- packages/core/src/agentbridge_core/application/run_lifecycle.py
```

Expected: PASS and no whitespace output.

- [ ] **Step 11: Commit**

```powershell
git add packages/core/src/agentbridge_core/application/run_lifecycle.py packages/core/src/agentbridge_core/errors.py packages/core/tests/application/test_approval_gate.py packages/core/tests/application/test_approval_execution.py
git commit -m "fix: harden approval resume lifecycle"
```

### Task 4: Recover expired pending approvals and expose a safe approval API

**Files:**
- Modify: `packages/core/src/agentbridge_core/application/run_lifecycle.py`
- Modify: `apps/api/config/settings.py`
- Modify: `apps/api/lifespan.py`
- Modify: `apps/api/routes/approvals.py`
- Modify: `apps/api/tests/test_approvals_api.py`
- Test: `packages/core/tests/application/test_approval_gate.py`

**Interfaces:**
- `RunLifecycle.expire_pending_approvals(*, now: datetime, limit: int = 100) -> int`.
- Setting `APPROVAL_EXPIRY_SCAN_INTERVAL_SECONDS`, default `30.0`, must be positive.
- Approval response DTO omits action, requester context, token, lease, internal error and DSN.

- [ ] **Step 1: Write pending-expiry recovery test**

Create one expired and one future pending action record, call:

```python
count = await lifecycle.expire_pending_approvals(now=now, limit=100)
assert count == 1
assert (await store.get(expired_id, tenant_id="acme"))["status"] == "denied"
assert (await store.get(future_id, tenant_id="acme"))["status"] == "pending"
run = await runs.get(expired_run_id, tenant_id="acme")
assert run and run["status"] == "done"
```

Assert EventLog contains `approval_resolved` with `reason="timeout"` followed by `done`.

- [ ] **Step 2: Verify expiry test RED**

Run the single test; expected failure is missing `expire_pending_approvals`.

- [ ] **Step 3: Implement Lifecycle expiry scan**

Call `list_expired_pending`, then reuse `finalize_approval(..., decision="deny", reason="timeout", sink=None)` for each record. Count only records that transition from pending.

When persisting a new approval, compute:

```python
now = datetime.now(timezone.utc)
approval_expires_at = now + timedelta(seconds=timeout_seconds)
```

and include it in the record.

- [ ] **Step 4: Write lifespan scanner cancellation test**

Add a settings validation test rejecting zero and negative scan intervals. Patch
the lifecycle scan method to set an `asyncio.Event`, run lifespan with interval
`0.01`, await the event with `asyncio.wait_for`, leave the context, and assert
the captured scanner task is cancelled and done without pending-task warnings.

- [ ] **Step 5: Implement the cancellable scanner**

In lifespan:

```python
async def _approval_expiry_loop() -> None:
    await lifecycle.expire_pending_approvals(now=datetime.now(timezone.utc))
    while True:
        await asyncio.sleep(settings.approval_expiry_scan_interval_seconds)
        await lifecycle.expire_pending_approvals(now=datetime.now(timezone.utc))
```

Create the task after Lifecycle construction; cancel and await it in `finally`, suppressing only `asyncio.CancelledError`.

- [ ] **Step 6: Write safe DTO tests**

After approval, assert:

```python
approval = response.json()["approval"]
assert set(approval) <= {
    "approval_id", "status", "decision", "reason",
    "run_id", "thread_id", "result",
}
for forbidden in (
    "action", "requester_context", "execution_token",
    "execution_lease_expires_at", "error",
):
    assert forbidden not in approval
```

Assert `ApprovalStateConflict` maps to HTTP 409:

```json
{"detail":{"code":"approval_state_conflict","message":"approval is executing"}}
```

- [ ] **Step 7: Implement Pydantic response models**

Define `ApprovalPublic` and `ApprovalDecisionResponse` in `routes/approvals.py`. Build the response from an allowlist, never by returning the store record directly.

- [ ] **Step 8: Run core/API approval tests**

```powershell
python -m pytest packages/core/tests/application/test_approval_gate.py apps/api/tests/test_approvals_api.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add packages/core/src/agentbridge_core/application/run_lifecycle.py apps/api/config/settings.py apps/api/lifespan.py apps/api/routes/approvals.py packages/core/tests/application/test_approval_gate.py apps/api/tests/test_approvals_api.py
git commit -m "feat: recover expired approvals safely"
```

### Task 5: Implement the read-only RAG-Agent PostgreSQL Retriever

**Files:**
- Create: `apps/api/adapters/rag_agent_pg_retriever.py`
- Modify: `apps/api/adapters/knowledge_backend.py`
- Modify: `apps/api/adapters/knowledge_ingest_factory.py`
- Modify: `apps/api/config/settings.py`
- Modify: `apps/api/tests/test_knowledge_backend_settings.py`
- Create: `apps/api/tests/test_rag_agent_pg_retriever.py`
- Modify: `.env.example`

**Interfaces:**

```python
class RagAgentPgRetriever:
    def __init__(
        self,
        *,
        dsn: str,
        demo_tenant: str,
        embed_api_base: str,
        embed_api_key: str,
        embed_model: str,
        embed_dimensions: int,
        pool: Any,
        client: httpx.AsyncClient,
        owns_pool: bool = False,
        owns_client: bool = False,
    ) -> None: ...

    @classmethod
    async def create(
        cls,
        *,
        dsn: str,
        demo_tenant: str,
        embed_api_base: str,
        embed_api_key: str,
        embed_model: str,
        embed_dimensions: int,
        pool: Any | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> "RagAgentPgRetriever": ...

    async def similarity_search(
        self, query: str, *, tenant_id: str, k: int = 5
    ) -> list[KnowledgeHit]: ...

    async def health_check(self) -> dict[str, Any]: ...
    async def close(self) -> None: ...
```

- [ ] **Step 1: Write non-demo tenant no-I/O test**

Use pool/client doubles that fail if called:

```python
class FailOnUse:
    def __getattr__(self, name: str) -> NoReturn:
        raise AssertionError(f"external dependency used: {name}")


@pytest.mark.asyncio
async def test_non_demo_tenant_returns_empty_without_external_io() -> None:
    retriever = RagAgentPgRetriever(
        dsn="unused",
        demo_tenant="rag-agent-demo",
        embed_api_base="http://unused/v1",
        embed_api_key="EMPTY",
        embed_model="BAAI/bge-m3",
        embed_dimensions=512,
        pool=FailOnUse(),
        client=FailOnUse(),
    )
    assert await retriever.similarity_search(
        "policy", tenant_id="other", k=3
    ) == []
```

- [ ] **Step 2: Write mapping and read-only query test**

The fake connection records transaction options and SQL, returning one row. Assert:

```python
assert connection.transaction_kwargs["readonly"] is True
assert "kb_document" in connection.sql
assert "kb_section" in connection.sql
assert "kb_chunk" in connection.sql
assert "$1::vector" in connection.sql
assert hits == [{
    "chunk_id": "chunk-1",
    "doc_id": "doc-1",
    "text": "policy text",
    "tenant_id": "rag-agent-demo",
    "score": pytest.approx(0.8),
    "metadata": {
        "title": "Policy",
        "section_id": "s1",
        "heading": "Scope",
        "source_backend": "rag_agent_pg",
    },
}]
```

The HTTP mock returns one 512-length embedding.

- [ ] **Step 3: Write schema and embedding dimension failure tests**

`create()` must raise `KnowledgeBackendUnavailable` when:

- any required table is absent;
- vector extension is absent;
- `format_type(...) != "vector(512)"`;
- embedding response length is not 512.

The exception message exposed to callers is stable; detailed probe values may be logged but not include DSN.

Also test runtime embedding HTTP failure and database query failure through
Lifecycle, asserting the stable `knowledge_backend_unavailable` code and safe
message defined in Task 3.

- [ ] **Step 4: Run Retriever tests and verify RED**

```powershell
python -m pytest apps/api/tests/test_rag_agent_pg_retriever.py -v
```

Expected: FAIL because adapter does not exist.

- [ ] **Step 5: Implement async embedding and mapping**

Use `httpx.AsyncClient.post(f"{base}/embeddings", json={"model": model, "input": [query]})`. Validate the response before SQL.

Use this query shape:

```sql
SELECT
    c.chunk_id,
    d.doc_id,
    c.content AS text,
    d.title,
    s.section_id,
    s.heading,
    1 - (c.embedding <=> $1::vector) AS score
FROM kb_document d
JOIN kb_section s ON s.document_id = d.id
JOIN kb_chunk c ON c.section_id = s.id
WHERE d.active_version = TRUE
  AND c.embedding IS NOT NULL
ORDER BY c.embedding <=> $1::vector
LIMIT $2
```

Run it inside `connection.transaction(readonly=True)`. Clamp scores to `[0.0, 1.0]`.

- [ ] **Step 6: Implement startup probes and lifecycle**

Probe using read-only SQL:

```sql
SELECT extversion FROM pg_extension WHERE extname = 'vector';
SELECT to_regclass('public.kb_document'),
       to_regclass('public.kb_section'),
       to_regclass('public.kb_chunk');
SELECT format_type(atttypid, atttypmod)
FROM pg_attribute
WHERE attrelid = 'kb_chunk'::regclass
  AND attname = 'embedding' AND NOT attisdropped;
```

The class owns and closes only clients/pools it created.

- [ ] **Step 7: Add Settings and factory validation**

Fields:

```python
rag_agent_pg_dsn: str = Field(default="", validation_alias="RAG_AGENT_PG_DSN")
rag_agent_demo_tenant: str = Field(
    default="rag-agent-demo", validation_alias="RAG_AGENT_DEMO_TENANT"
)
rag_agent_embed_api_base: str = Field(
    default="http://127.0.0.1:8080/v1",
    validation_alias="RAG_AGENT_EMBED_API_BASE",
)
rag_agent_embed_api_key: str = Field(
    default="EMPTY", validation_alias="RAG_AGENT_EMBED_API_KEY"
)
rag_agent_embed_model: str = Field(
    default="BAAI/bge-m3", validation_alias="RAG_AGENT_EMBED_MODEL"
)
rag_agent_embed_dimensions: int = Field(
    default=512, validation_alias="RAG_AGENT_EMBED_DIMENSIONS"
)
```

`validate_rag_agent_pg_settings` requires DSN, tenant, base URL, model and positive dimensions. `build_retriever` creates the adapter only for `rag_agent_pg`. `knowledge_ingest_factory` returns `UnsupportedKnowledgeIngest("rag_agent_pg")`.

- [ ] **Step 8: Run adapter/factory tests**

```powershell
python -m pytest apps/api/tests/test_rag_agent_pg_retriever.py apps/api/tests/test_knowledge_backend_settings.py apps/api/tests/test_ingest_api.py -v
```

Expected: PASS without a real database.

- [ ] **Step 9: Commit**

```powershell
git add apps/api/adapters/rag_agent_pg_retriever.py apps/api/adapters/knowledge_backend.py apps/api/adapters/knowledge_ingest_factory.py apps/api/config/settings.py apps/api/tests/test_rag_agent_pg_retriever.py apps/api/tests/test_knowledge_backend_settings.py .env.example
git commit -m "feat: add readonly rag agent retriever"
```

### Task 6: Rebuild work_order_ops around guarded tools and dynamic drafts

**Files:**
- Modify: `apps/api/domains/work_order_ops/state.py`
- Modify: `apps/api/domains/work_order_ops/tools.py`
- Modify: `apps/api/domains/work_order_ops/graph.py`
- Modify: `apps/api/domains/work_order_ops/bootstrap.py`
- Create: `apps/api/migrations/007_work_order_demo_tenant.sql`
- Modify: `apps/api/tests/test_work_order_ops.py`

**Interfaces:**
- Graph input:

```python
{
    "messages": [{"role": "user", "content": query}],
    "model_alias": model,
    "structured_draft": extra.get("work_order_draft"),
}
```

- Graph builder must use only `tools` passed by `LangGraphRuntime`.
- Both natural-language and structured paths invoke the guarded `prepare_work_order_draft`.

- [ ] **Step 1: Write structured-draft end-to-end test**

POST:

```json
{
  "query": "创建工单",
  "thread_id": "wo-structured",
  "route": "work_order_ops",
  "extra": {
    "work_order_draft": {
      "title": "园区网络告警",
      "priority": "high",
      "assignee_id": "assignee-rag-demo",
      "ledger_summary": "用户报告园区网络中断，需立即排查"
    }
  }
}
```

Assert:

```python
assert preview["data"]["work_order"]["title"] == "园区网络告警"
assert required["data"]["action"]["payload"]["title"] == "园区网络告警"
assert required["data"]["action"]["payload"]["assignee_id"] == "assignee-rag-demo"
assert "脱敏工单草稿" not in response.text
```

After approval, query FakeDataSource and assert the same title, priority, assignee and ledger summary were written.

- [ ] **Step 2: Write natural-language tool-call test**

Inject a gateway whose `chat(..., tools, tool_choice)` returns:

```python
AIMessage(
    content="",
    tool_calls=[{
        "name": "prepare_work_order_draft",
        "args": {
            "title": "温室设备异常",
            "priority": "medium",
            "assignee_id": "assignee-rag-demo",
            "ledger_summary": "温室传感器连续离线",
        },
        "id": "tc-draft-1",
        "type": "tool_call",
    }],
)
```

Assert the gateway received only the guarded draft tool and the resulting approval payload uses those values.

- [ ] **Step 3: Write missing-permission and audit tests**

Construct contexts missing each permission. Assert:

- missing `workorder:read`: no list/stat tool call;
- missing `knowledge:read`: retriever not called;
- missing create or assign: gateway does not receive draft tool and no approval event;
- direct invocation of a guarded unavailable tool is denied and audited.

- [ ] **Step 4: Write missing-field and assignee tests**

- LLM response without the draft tool call produces a user-facing request for missing fields and no approval.
- Structured draft missing `priority` produces stable validation error and no approval.
- Inactive/cross-tenant assignee produces no preview or approval.

- [ ] **Step 5: Run work-order tests and verify RED**

```powershell
python -m pytest apps/api/tests/test_work_order_ops.py -v
```

Expected: fixed draft and direct Port access make the new tests fail.

- [ ] **Step 6: Implement input/state changes**

Define state fields for `model_alias`, `structured_draft` and messages. Replace the lambda input builder with a named function that copies only `extra["work_order_draft"]`; do not checkpoint arbitrary `extra`.

- [ ] **Step 7: Implement graph nodes using guarded tools**

Use these nodes:

```text
START
  → plan_reads
  → read_tools
  → plan_draft
  → draft_tools (conditional)
  → present
  → END
```

- `plan_reads` creates tool calls only for names present in passed `tools`.
- `read_tools` is `ToolNode(guarded_tools)`.
- `plan_draft` uses structured input or `llm_gateway.chat(... tools=[guarded_prepare])`.
- `draft_tools` executes the returned call with the same `ToolNode`.
- `present` parses ToolMessages and creates list/chart/citation/preview/action events.
- Delete all direct DataSource/Retriever access and permission-string checks from `graph.py`.
- Never fall back to module-level raw tools when a filtered tool is absent.

- [ ] **Step 8: Validate assignee in the draft tool**

Before returning `CreateWorkOrderDraft.model_dump()`, query:

```sql
SELECT * FROM assignees WHERE id = $1 AND tenant_id = $2
```

using `ctx.tenant_id`. Reject missing/inactive assignees. Approval handler retains the same check inside its transaction.

- [ ] **Step 9: Add migration 007**

Insert idempotent synthetic records:

```sql
INSERT INTO assignees (id, tenant_id, name, team, active, specialties)
VALUES (
    'assignee-rag-demo', 'rag-agent-demo',
    '演示处理员', '演示运营组', TRUE, 'equipment'
)
ON CONFLICT (id) DO NOTHING;
```

Also add one work order and ledger for `rag-agent-demo`, using fixed synthetic IDs and no real names, addresses, phones or customer identifiers.

- [ ] **Step 10: Run domain and policy tests**

```powershell
$env:KNOWLEDGE_BACKEND='fake'
python -m pytest apps/api/tests/test_work_order_ops.py apps/api/tests/test_demo_readonly_policy.py apps/api/tests/test_demo_rag.py -v
```

Expected: PASS.

- [ ] **Step 11: Commit**

```powershell
git add apps/api/domains/work_order_ops apps/api/migrations/007_work_order_demo_tenant.sql apps/api/tests/test_work_order_ops.py
git commit -m "feat: make work order flow tool driven"
```

### Task 7: Complete failure, rollback, compatibility, and PostgreSQL recovery coverage

**Files:**
- Modify: `apps/api/tests/test_work_order_ops.py`
- Modify: `apps/api/tests/test_postgres_approval_store.py`
- Modify: `apps/api/tests/test_postgres_data_source.py`
- Modify: `packages/core/tests/application/test_approval_gate.py`

**Interfaces:**
- No new production interface; this task closes the approved Spec test matrix.

- [ ] **Step 1: Add deny/timeout/permission/cross-tenant API tests**

For each scenario assert:

```python
assert await source.query(
    "SELECT * FROM work_orders WHERE tenant_id = $1", tenant_id
) == []
assert await source.query(
    "SELECT * FROM ledgers WHERE tenant_id = $1", tenant_id
) == []
assert not any(e["type"] == "x.work_order_ops.work_order_created" for e in events)
```

Cover deny, timeout, requester permission removal before approve, approver without `approval:decide`, cross-tenant approval ID and missing create/assign permission.

- [ ] **Step 2: Add second-write rollback test**

Create a `TransactionalDataSource` test double that raises on the ledger INSERT after accepting the work-order INSERT inside its transactional snapshot. Assert both tables remain empty.

- [ ] **Step 3: Add concurrent approve test**

Call `finalize_approval` concurrently with two sinks. Assert one action execution, one work order, one ledger and one created event in EventLog.

- [ ] **Step 4: Add EventLog delivery-failure test**

Fail EventLog append after business commit. Assert:

```python
approval = await approvals.get(approval_id, tenant_id="rag-agent-demo")
assert approval["status"] == "succeeded"
assert approval["result_delivery_error"]
run = await runs.get(run_id, tenant_id="rag-agent-demo")
assert run["status"] == "done"
assert run["result_delivery_error"]
assert len(work_orders) == len(ledgers) == 1
```

Retry must not create another row.

- [ ] **Step 5: Add old-client compatibility test**

Filter out all events whose type starts with `x.work_order_ops.` and assert the remaining stream still has `start`, stable approval/error events as applicable, and terminal `done`.

- [ ] **Step 6: Replace the incomplete PG recovery test**

Apply migrations `004`, `005`, `006`, `007`. Use real `PostgresApprovalStore`, `PostgresDataSource`, action registry and Lifecycle:

1. create and approve the action;
2. claim with a one-second lease;
3. execute the business handler and commit;
4. intentionally skip `mark_succeeded`;
5. close both first-instance adapters;
6. create new store/data-source/registry/lifecycle instances;
7. recover after lease expiry and approve again;
8. assert one work order, one ledger, `succeeded`, and the reconstructed result equals the first handler result.

Do not reduce this to calling the handler twice without ApprovalStore/Lifecycle.

- [ ] **Step 7: Run the complete automated matrix**

```powershell
$env:KNOWLEDGE_BACKEND='fake'
python -m pytest packages/core/tests/application/test_approval_gate.py packages/core/tests/application/test_approval_execution.py apps/api/tests/test_work_order_ops.py apps/api/tests/test_postgres_approval_store.py apps/api/tests/test_postgres_data_source.py -v
```

Expected: all non-PG tests pass; PG tests pass with `AGENTBRIDGE_TEST_PG_DSN`, otherwise are explicitly reported as skipped.

- [ ] **Step 8: Commit**

```powershell
git add packages/core/tests/application/test_approval_gate.py apps/api/tests/test_work_order_ops.py apps/api/tests/test_postgres_approval_store.py apps/api/tests/test_postgres_data_source.py
git commit -m "test: close work order failure matrix"
```

### Task 8: Add a credential-safe real RAG-Agent acceptance probe

**Files:**
- Create: `scripts/verify_rag_agent_readonly.py`
- Create: `apps/api/tests/test_verify_rag_agent_readonly.py`
- Modify: `apps/api/domains/work_order_ops/README.md`
- Modify: `docs/knowledge-base.md`

**Interfaces:**
- Script consumes only AgentBridge `RAG_AGENT_*` environment variables.
- Script output contains backend status, vector dimension, hit count, citation IDs and latency; never DSN, credentials, embeddings or document text.

- [ ] **Step 1: Write output-redaction unit test**

Extract a pure formatter:

```python
def acceptance_summary(
    *, hit_count: int, citations: list[dict[str, Any]], latency_ms: int
) -> dict[str, Any]:
    ...
```

Test that output keys are exactly:

```python
{"status", "tenant_id", "hit_count", "citation_ids", "latency_ms"}
```

and serialized output does not contain `text`, `embedding`, `dsn`, `password` or the supplied sample document body.

Load the script module in the test with
`importlib.util.spec_from_file_location`; do not turn `scripts/` into an
application package merely for this test.

- [ ] **Step 2: Verify RED, then implement the script**

The script:

1. prepends the repository `apps/api` directory to `sys.path`, following the
   existing standalone script convention, then loads `Settings`;
2. requires `KNOWLEDGE_BACKEND=rag_agent_pg`;
3. builds the retriever through `build_retriever`;
4. probes query `现代农业产业园政策支持`;
5. verifies `rag-agent-demo` returns at least one normalized citation;
6. verifies tenant `other` returns empty;
7. closes the retriever in `finally`;
8. exits non-zero on any failed assertion.

- [ ] **Step 3: Document the read-only account and run command**

Document:

```powershell
$env:KNOWLEDGE_BACKEND='rag_agent_pg'
$env:RAG_AGENT_PG_DSN='由本机安全环境提供'
$env:RAG_AGENT_DEMO_TENANT='rag-agent-demo'
$env:RAG_AGENT_EMBED_API_BASE='http://127.0.0.1:8080/v1'
$env:RAG_AGENT_EMBED_MODEL='BAAI/bge-m3'
$env:RAG_AGENT_EMBED_DIMENSIONS='512'
python scripts/verify_rag_agent_readonly.py
```

The literal DSN must not be committed.

- [ ] **Step 4: Run automated probe tests**

```powershell
python -m pytest apps/api/tests/test_rag_agent_pg_retriever.py apps/api/tests/test_verify_rag_agent_readonly.py -v
```

Expected: PASS.

- [ ] **Step 5: Run the real read-only acceptance**

Use the existing RAG-Agent environment to provide the DSN without printing it. Expected evidence:

- pgvector version detected;
- `vector(512)` detected;
- embedding vector length 512;
- demo tenant hit count greater than zero;
- other tenant hit count zero;
- no data mutation command executed.

- [ ] **Step 6: Commit**

```powershell
git add scripts/verify_rag_agent_readonly.py apps/api/tests/test_verify_rag_agent_readonly.py apps/api/domains/work_order_ops/README.md docs/knowledge-base.md
git commit -m "test: verify readonly rag agent integration"
```

### Task 9: Align release status, migration docs, and full quality gates

**Files:**
- Modify: `apps/api/migrations/README.md`
- Modify: `docs/contracts.md`
- Modify: `docs/release-plan.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/releases/v0.1.0-tech-preview.md`
- Modify: `.env.example`

**Interfaces:**
- Documentation must say “P1 implementation complete only after real PG/RAG acceptance evidence”; it must not say “P1 not delivered” once those gates pass.

- [ ] **Step 1: Write document consistency assertions**

```powershell
$release = Get-Content -Raw docs/releases/v0.1.0-tech-preview.md
$plan = Get-Content -Raw docs/release-plan.md
$kb = Get-Content -Raw docs/knowledge-base.md
foreach ($term in @('实现已合入', '真实 PG/RAG 验收', 'rag_agent_pg', 'rag-agent-demo', '只读')) {
    if (($release + $plan + $kb) -notmatch [regex]::Escape($term)) {
        throw "missing release term: $term"
    }
}
if ($release -match 'P1 工单黄金案例尚未交付') {
    throw 'stale P1 status'
}
```

- [ ] **Step 2: Verify assertion RED**

Expected: stale P1 status or missing `rag_agent_pg`.

- [ ] **Step 3: Update docs and migration ordering**

- Document `006` and `007` after `005`.
- Add `rag_agent_pg` to the support matrix as a read-only, fixed-demo-tenant integration.
- Link the hardening Spec and this plan from the domain README.
- State that RAG-Agent source/data remain untouched.
- Keep `v0.1.0` as technical preview; P2/P3 and security channel still block stable/public release.

- [ ] **Step 4: Re-run document assertions and link checks**

```powershell
rg -n "006_approval_hardening|007_work_order_demo_tenant|rag_agent_pg|rag-agent-demo" apps/api/migrations/README.md .env.example docs apps/api/domains/work_order_ops/README.md
git diff --check
```

Expected: terms present, no whitespace errors.

- [ ] **Step 5: Run full automated gates**

The repository currently has pre-existing Ruff debt outside this change set.
Run Ruff over every production and test path touched by this plan, while keeping
the repository-wide architecture and test gates:

```powershell
$env:KNOWLEDGE_BACKEND='fake'
python -m pytest packages/core/tests apps/api/tests -q
python -m ruff check `
  packages/core/src/agentbridge_core/ports/llm_gateway.py `
  packages/core/src/agentbridge_core/ports/approval.py `
  packages/core/src/agentbridge_core/adapters/direct_llm_gateway.py `
  packages/core/src/agentbridge_core/adapters/alias_llm_gateway.py `
  packages/core/src/agentbridge_core/adapters/memory_approval_store.py `
  packages/core/src/agentbridge_core/application/run_lifecycle.py `
  packages/core/src/agentbridge_core/errors.py `
  packages/core/tests/adapters/test_direct_llm_gateway.py `
  packages/core/tests/adapters/test_alias_llm_gateway.py `
  packages/core/tests/application/test_approval_execution.py `
  packages/core/tests/application/test_approval_gate.py `
  apps/api/adapters/rag_agent_pg_retriever.py `
  apps/api/adapters/knowledge_backend.py `
  apps/api/adapters/knowledge_ingest_factory.py `
  apps/api/adapters/postgres_approval_store.py `
  apps/api/config/settings.py apps/api/lifespan.py `
  apps/api/routes/approvals.py apps/api/domains/work_order_ops `
  apps/api/tests/test_rag_agent_pg_retriever.py `
  apps/api/tests/test_verify_rag_agent_readonly.py `
  apps/api/tests/test_knowledge_backend_settings.py `
  apps/api/tests/test_postgres_approval_store.py `
  apps/api/tests/test_approvals_api.py `
  apps/api/tests/test_work_order_ops.py `
  scripts/verify_rag_agent_readonly.py
python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
python scripts/import_scan_core.py
python scripts/import_scan_rag_engines.py
git diff --check
```

Expected: zero failures. Record PostgreSQL skips by name; do not describe skipped tests as passed.

- [ ] **Step 6: Run real PostgreSQL and RAG gates**

With safe local environment variables:

```powershell
python -m pytest apps/api/tests/test_postgres_approval_store.py apps/api/tests/test_postgres_data_source.py apps/api/tests/test_work_order_ops.py -v
python scripts/verify_rag_agent_readonly.py
```

Expected: PG lifecycle recovery passes; RAG demo tenant returns citations; other tenant returns none.

- [ ] **Step 7: Review architecture boundaries**

```powershell
rg -n "agentbridge_core\.adapters|from adapters|EventSink" apps/api/domains/work_order_ops
rg -n "work_order_ops|rag_agent|工单|kb_chunk" packages/core/src/agentbridge_core
```

Expected: first command has no forbidden domain adapter/EventSink imports; second has no business/RAG-Agent schema names in core.

- [ ] **Step 8: Commit**

```powershell
git add .env.example apps/api/migrations/README.md docs/contracts.md docs/knowledge-base.md docs/release-plan.md docs/roadmap.md docs/releases/v0.1.0-tech-preview.md apps/api/domains/work_order_ops/README.md
git commit -m "docs: complete p1 hardening acceptance"
```

## Spec Traceability

| Design requirement | Delivering tasks | Acceptance evidence |
|---|---:|---|
| §2 boundary: do not modify RAG-Agent; fixed `rag-agent-demo`; preserve existing backends | 5, 8, 9 | no-I/O cross-tenant test, factory compatibility tests, read-only live probe |
| §3 architecture and composition-root ownership | 1, 4, 5, 6 | import-linter, import scans, boundary grep |
| §4 dynamic drafts and one immutable action payload | 6 | natural-language and structured-draft end-to-end tests |
| §5 guarded tool visibility and invocation-time authorization | 1, 6, 7 | missing-permission and denial-audit tests |
| §6 read-only Retriever, schema probes and safe failure semantics | 3, 5, 8 | adapter unit tests plus real pgvector/embedding acceptance |
| §7 fencing, sequence, projection, decision and pending timeout | 2, 3, 4, 7 | Memory/PostgreSQL recovery matrix and Lifecycle projection tests |
| §8 safe approval DTO and stable public errors | 3, 4, 5 | API allowlist and redaction tests |
| §9 automated, PostgreSQL and real RAG acceptance | 7, 8, 9 | full pytest/architecture gates and credential-safe probe |
| §10 append-only migrations `006`/`007` | 2, 6, 9 | migration integration tests and ordering documentation |
| §11 non-goals | all | diff review confirms no RAG-Agent mutation, ingestion or new RAG API |

## Final Plan Audit

- [ ] Map every requirement in `docs/superpowers/specs/2026-07-30-p1-hardening-rag-agent-integration-design.md` to Tasks 1–9.
- [ ] Confirm all new production behavior has a test that was observed failing before implementation.
- [ ] Confirm `git status --short` is clean.
- [ ] Confirm real RAG evidence contains no DSN, password, embedding vector or document body.
- [ ] Request an independent code review of the full base-to-head diff.
- [ ] Use `superpowers:verification-before-completion` before any completion claim.
- [ ] Use `superpowers:finishing-a-development-branch` only after all automated and real-environment gates pass.
