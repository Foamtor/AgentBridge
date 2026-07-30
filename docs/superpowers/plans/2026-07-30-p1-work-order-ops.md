# P1 工单运营助手黄金案例 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 `work_order_ops` 参考 domain：基于脱敏数据完成工单查询、RAG 引用、结构化列表/图表/台账预览，以及经人工审批后幂等地创建工单与台账。

**Architecture:** core 增加不含业务名的事务 Port、审批执行状态机和审批恢复 executor Port；API 宿主在 `lifespan.py` 先创建数据源、再组装 registry，并把同一个 Port 注入 domain 的审批 handler。查询/RAG 工具继续从当前 `RunContext.metadata` 取得已注入 Port；审批 handler 绝不从已持久化的上下文恢复 metadata。业务结果经 `OutboundFragment` 和 `OUTBOUND_EXTENSIONS_KEY` 进入既有 EventLog-before-SSE 生命周期。

**Tech Stack:** Python 3.12+, FastAPI, LangGraph, Pydantic v2, asyncpg, PostgreSQL, LangChain Core, pytest/pytest-asyncio。

## Global Constraints

- `agentbridge_core.application` 不 import adapters；core 源码不得出现 `work_order_ops`、工单、表名或业务权限字符串。
- domain 不创建 adapter、不 import adapter 实现、不持有 `EventSink`；扩展事件只能经 `OUTBOUND_EXTENSIONS_KEY` 输出。
- adapter 与 registry 实例只在 `apps/api/lifespan.py` 创建并注入。
- 无权限工具不进模型列表；执行与审批恢复时都必须再次 `Policy.decide`。
- 需要多项权限的动作必须使用通用 `required_permissions_all`；`workorder:create` 与 `workorder:assign` 缺任一项均不可见、不可调用、不可经审批恢复。
- 数据库 `tenant_id` 只来自 `RunContext` 或审批记录，不能来自模型 payload。
- `approval_id` 是业务写入幂等键；`work_orders` 和 `ledgers` 必须在单一事务中写入。
- 稳定 SSE 类型不变；新增事件仅为 `x.work_order_ops.*`，每个 payload 包含 `schema_version: 1`。
- 审批记录必须持久化 `route`、run/thread/tenant、审批序号、完整 action envelope 和请求人安全快照；快照只含 user_id、tenant_id、roles、permissions、预算、policy_bundle_version，绝不含 metadata、客户端或 token map。
- `work_order_ops.create_v1` 的审批 handler 只能由 domain bootstrap 以 `TransactionalDataSource` 构造后登记；registry 不 import domain，core 不知晓该 handler 或其业务资源。
- P1 参考案例和重启恢复验收必须设置 `APPROVAL_STORE_BACKEND=postgres`；`memory` 只允许 CI/本地体验，不可作为崩溃恢复证据。

---

## 文件结构

- Modify: `packages/core/src/agentbridge_core/ports/data_source.py` — 事务协议。
- Modify: `packages/core/src/agentbridge_core/adapters/{fake_data_source,noop_data_source}.py`、`apps/api/adapters/postgres_data_source.py` — 事务实现。
- Modify: `packages/core/src/agentbridge_core/protocol/tool_meta.py`、`adapters/role_policy.py`、`application/tool_guard.py` — 通用全量权限元数据和双检语义。
- Create: `packages/core/src/agentbridge_core/ports/approval_resume.py` — 通用 action executor Port。
- Modify: `packages/core/src/agentbridge_core/ports/approval.py`、`adapters/memory_approval_store.py`、`application/run_lifecycle.py` — 审批状态、恢复执行。
- Create: `apps/api/adapters/approval_action_registry.py` — `(route, action.type)` registry。
- Create: `apps/api/adapters/postgres_approval_store.py` — 持久化审批与执行租约 adapter。
- Modify: `apps/api/config/settings.py`、`apps/api/lifespan.py`、`apps/api/routes/approvals.py`、`apps/api/domains/bootstrap.py` — 宿主接线与测试 Port 注入。
- Create: `apps/api/domains/work_order_ops/{__init__,state,tools,graph,approval,bootstrap,README}.py` — 黄金 domain。
- Create: `apps/api/migrations/004_approval_execution.sql` — 通用审批记录与租约 schema。
- Create: `apps/api/migrations/005_work_order_ops.sql` — 脱敏表、幂等约束和种子。
- Create: `packages/core/tests/application/test_approval_execution.py`、`apps/api/tests/test_work_order_ops.py`、`apps/api/tests/test_approval_action_registry.py`、`apps/api/tests/test_postgres_approval_store.py`。
- Modify: `packages/core/tests/adapters/test_fake_data_source.py`、`packages/core/tests/adapters/test_role_policy.py`、`packages/core/tests/application/test_approval_gate.py`、`packages/core/tests/application/test_tool_guard.py`、`apps/api/tests/test_postgres_data_source.py`、`apps/api/migrations/README.md`、`docs/contracts.md`、`docs/knowledge-base.md`、`docs/add-a-domain.md`。

### Task 1: 事务性数据访问 Port 与适配器

**Files:**
- Modify: `packages/core/src/agentbridge_core/ports/data_source.py`
- Modify: `packages/core/src/agentbridge_core/adapters/fake_data_source.py`
- Modify: `packages/core/src/agentbridge_core/adapters/noop_data_source.py`
- Modify: `apps/api/adapters/postgres_data_source.py`
- Test: `packages/core/tests/adapters/test_fake_data_source.py`
- Test: `apps/api/tests/test_postgres_data_source.py`

**Consumes:** 现有 `DataSource.query(sql, *params)` / `execute(sql, *params)`。

**Produces:** `TransactionalDataSource.transaction(operation)`；operation 接收仅在同一事务有效的 DataSource 会话。

- [ ] **Step 1: 写出 Fake 回滚失败测试**

```python
@pytest.mark.asyncio
async def test_fake_transaction_rolls_back_on_error() -> None:
    ds = FakeDataSource()
    ds.seed("items", [{"id": "before", "tenant_id": "acme"}])
    async def operation(tx):
        await tx.execute("INSERT INTO items (id, tenant_id) VALUES ($1, $2)", "after", "acme")
        raise RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        await ds.transaction(operation)
    assert await ds.query("SELECT * FROM items WHERE tenant_id = $1", "acme") == [{"id": "before", "tenant_id": "acme"}]
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest packages/core/tests/adapters/test_fake_data_source.py::test_fake_transaction_rolls_back_on_error -v`

Expected: FAIL，`FakeDataSource` 没有 `transaction`。

- [ ] **Step 3: 定义 Port 并实现 Fake/Noop**

在 `data_source.py` 定义：

```python
T = TypeVar("T")
class TransactionalDataSource(DataSource, Protocol):
    async def transaction(self, operation: Callable[[DataSource], Awaitable[T]]) -> T:
        pass
```

Fake 在 operation 前以 `copy.deepcopy(self._tables)` 保存快照；捕获 `BaseException` 时恢复快照并重抛。扩展 Fake `execute`，仅支持测试所需的参数化 `INSERT INTO <table> (<columns>) VALUES (<one bound parameter per listed column>)`，将参数映射为新行；不匹配语法抛 `ValueError`。Noop 的 transaction 调用 `await operation(self)`。

- [ ] **Step 4: 实现 Postgres 同连接事务**

新增私有 `_PostgresTransaction`，持有已 acquire 的 asyncpg connection 并实现 `query`/`execute`。新增：

```python
async def transaction(self, operation):
    pool = await self._ensure_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await operation(_PostgresTransaction(conn))
```

在 PG 集成测试中 INSERT 后抛错，最后查询断言没有该行。

- [ ] **Step 5: 运行相关测试**

Run: `python -m pytest packages/core/tests/adapters/test_fake_data_source.py -v; python -m pytest apps/api/tests/test_postgres_data_source.py -v`

Expected: Fake 通过；未设 `AGENTBRIDGE_TEST_PG_DSN` 的 Postgres 测试按既有策略 skip。

- [ ] **Step 6: 提交**

Run: `git add packages/core/src/agentbridge_core/ports/data_source.py packages/core/src/agentbridge_core/adapters/fake_data_source.py packages/core/src/agentbridge_core/adapters/noop_data_source.py packages/core/tests/adapters/test_fake_data_source.py apps/api/adapters/postgres_data_source.py apps/api/tests/test_postgres_data_source.py; git commit -m "feat: add transactional data source port"`

### Task 2: 通用全量权限与调用期双检

**Files:**
- Modify: `packages/core/src/agentbridge_core/protocol/tool_meta.py`
- Modify: `packages/core/src/agentbridge_core/adapters/role_policy.py`
- Modify: `packages/core/src/agentbridge_core/application/tool_guard.py`
- Test: `packages/core/tests/adapters/test_role_policy.py`
- Test: `packages/core/tests/application/test_tool_guard.py`

**Consumes:** 现有 `attach_tool_meta`、`get_tool_meta`、`RolePolicyEngine` 和 `guard_tools`。

**Produces:** `required_permissions_all: list[str]`；保留既有 `required_permissions` 的“任一满足”兼容语义，但当 `required_permissions_all` 非空时必须全部满足。

- [ ] **Step 1: 写出同时缺失一项权限的失败测试**

```python
def write() -> None:
    return None

def test_policy_requires_all_declared_permissions() -> None:
    tool = attach_tool_meta(
        write,
        required_permissions_all=["perm:create", "perm:assign"],
    )
    ctx = RunContext(user_id="u", tenant_id="acme", permissions=["perm:create"])
    assert RolePolicyEngine().filter_tools("route", [tool], ctx) == []
    assert RolePolicyEngine().decide(
        ctx=ctx,
        action="invoke_tool",
        resource={
            "name": "write",
            "required_roles": [],
            "required_permissions": [],
            "required_permissions_all": ["perm:create", "perm:assign"],
        },
    ) == "deny"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest packages/core/tests/adapters/test_role_policy.py::test_policy_requires_all_declared_permissions -v`

Expected: FAIL；`attach_tool_meta` 尚不接受 `required_permissions_all`。

- [ ] **Step 3: 实现通用 all-of 元数据**

将 `attach_tool_meta` 和 `get_tool_meta` 增加 `required_permissions_all`，默认空列表；`_resource_for` 将该字段带入调用期 Policy resource。修改 `RolePolicyEngine._allowed`：`*` 仍允许；若 `required_permissions_all` 非空且不是 `set(required_permissions_all) <= set(ctx.permissions)`，立即拒绝；随后沿用既有 roles 与 `required_permissions` 的任一满足逻辑。不得改变仅使用旧 `required_permissions` 的已有 domain 行为。

- [ ] **Step 4: 增加列表过滤和调用期拒绝测试**

覆盖仅有 create、仅有 assign、同时拥有两项和 `*` 四种上下文；前两种同时断言 `filter_tools` 不暴露工具、`guard_tools` 在直接调用时不执行原工具并记录 denied audit，后两种允许。保留一个仅使用旧 `required_permissions` 的回归断言，证明其仍是任一满足。

- [ ] **Step 5: 运行权限测试**

Run: `python -m pytest packages/core/tests/adapters/test_role_policy.py packages/core/tests/application/test_tool_guard.py -v`

Expected: PASS。

- [ ] **Step 6: 提交**

Run: `git add packages/core/src/agentbridge_core/protocol/tool_meta.py packages/core/src/agentbridge_core/adapters/role_policy.py packages/core/src/agentbridge_core/application/tool_guard.py packages/core/tests/adapters/test_role_policy.py packages/core/tests/application/test_tool_guard.py; git commit -m "feat: support all-required tool permissions"`

### Task 3: 审批 action 状态机与恢复 executor Port

**Files:**
- Create: `packages/core/src/agentbridge_core/ports/approval_resume.py`
- Modify: `packages/core/src/agentbridge_core/ports/approval.py`
- Modify: `packages/core/src/agentbridge_core/adapters/memory_approval_store.py`
- Test: `packages/core/tests/application/test_approval_execution.py`

**Consumes:** `RunContext`、`OutboundFragment`、MemoryApprovalStore 的租户隔离。

**Produces:** 原子 `claim_execution`、`mark_succeeded`、`mark_retryable_failed` 与 route/action 解析的 `ApprovalResumeExecutor` / `ApprovalActionHandler` / `ApprovalActionRegistrar` Protocol。

- [ ] **Step 1: 写出并发 claim 的失败测试**

```python
from datetime import UTC, datetime

@pytest.mark.asyncio
async def test_approval_claim_is_single_consumer() -> None:
    t0 = datetime(2026, 7, 30, tzinfo=UTC)
    store = MemoryApprovalStore()
    aid = await store.create({"tenant_id": "acme", "status": "approved_pending_execution"})
    first, second = await asyncio.gather(
        store.claim_execution(aid, tenant_id="acme", now=t0, lease_seconds=60),
        store.claim_execution(aid, tenant_id="acme", now=t0, lease_seconds=60),
    )
    assert sum(item is not None for item in (first, second)) == 1
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest packages/core/tests/application/test_approval_execution.py::test_approval_claim_is_single_consumer -v`

Expected: FAIL，`claim_execution` 未定义。

- [ ] **Step 3: 定义 Port 与内存状态机**

在 `approval.py` 扩展 Protocol，方法签名为：

```python
async def decide(self, approval_id: str, *, tenant_id: str, decision: str, reason: str | None = None) -> dict[str, Any] | None:
    pass
async def claim_execution(self, approval_id: str, *, tenant_id: str, now: datetime, lease_seconds: float) -> dict[str, Any] | None:
    pass
async def mark_succeeded(self, approval_id: str, *, tenant_id: str, result: dict[str, Any]) -> dict[str, Any] | None:
    pass
async def mark_retryable_failed(self, approval_id: str, *, tenant_id: str, error: str) -> dict[str, Any] | None:
    pass
async def mark_execution_denied(self, approval_id: str, *, tenant_id: str, reason: str) -> dict[str, Any] | None:
    pass
async def mark_result_delivery_failed(self, approval_id: str, *, tenant_id: str, error: str) -> dict[str, Any] | None:
    pass
async def recover_expired_execution(self, approval_id: str, *, tenant_id: str, now: datetime) -> dict[str, Any] | None:
    pass
```

approve 将 pending 改为 `approved_pending_execution` 并持久化 `decision="approve"`；deny/timeout 改为 `denied` 并持久化传入的 `reason`（HTTP deny 默认 `deny`、内部 timeout 为 `timeout`）。`mark_execution_denied` 仅允许从 `approved_pending_execution` 转为 `denied`，用于请求人 Policy 复检失败、route/action 无 handler 或 action schema 不支持；它必须持久化拒绝原因。claim 仅允许 `approved_pending_execution`、`retryable_failed`，并写入 `execution_started_at` 与 `execution_lease_expires_at` 后改为 `executing`。`recover_expired_execution` 仅在执行租约到期时将 `executing` 改为 `retryable_failed`，随后才能再次 claim。所有检查与修改必须在 MemoryApprovalStore 同一 `asyncio.Lock` 内。

在新 `approval_resume.py` 定义：

```python
class ApprovalResumeExecutor(Protocol):
    def resource_for(self, *, route: str, action: dict[str, Any]) -> dict[str, Any]:
        pass
    async def execute(self, *, route: str, action: dict[str, Any], requester_ctx: RunContext, approval_id: str) -> list[OutboundFragment]:
        pass

class ApprovalActionHandler(Protocol):
    async def __call__(self, *, action: dict[str, Any], requester_ctx: RunContext, approval_id: str) -> list[OutboundFragment]:
        pass

class ApprovalActionRegistrar(Protocol):
    def register(self, route: str, action_type: str, handler: ApprovalActionHandler, resource: dict[str, Any]) -> None:
        pass
```

- [ ] **Step 4: 增加状态转移测试**

覆盖 approve→claim→succeeded、执行失败→retryable_failed→再次 claim、deny 不可 claim、审批后 Policy deny→execution_denied、跨租户返回 None、未到期 executing 不可重入、到期 executing→retryable_failed→再次 claim，以及 succeeded→结果投递失败仍不可 claim；每项断言 result、error、拒绝原因、执行租约或 `result_delivery_error` 被持久化。

- [ ] **Step 5: 运行相关测试**

Run: `python -m pytest packages/core/tests/application/test_approval_execution.py -v`

Expected: PASS。

- [ ] **Step 6: 提交**

Run: `git add packages/core/src/agentbridge_core/ports/approval.py packages/core/src/agentbridge_core/ports/approval_resume.py packages/core/src/agentbridge_core/adapters/memory_approval_store.py packages/core/tests/application/test_approval_execution.py; git commit -m "feat: add approval execution state machine"`

### Task 4: PostgreSQL 审批持久化与崩溃恢复

**Files:**
- Create: `apps/api/migrations/004_approval_execution.sql`
- Create: `apps/api/adapters/postgres_approval_store.py`
- Modify: `apps/api/config/settings.py`
- Modify: `apps/api/migrations/README.md`
- Test: `apps/api/tests/test_postgres_approval_store.py`

**Consumes:** Task 3 的 `ApprovalStore` 状态方法、通用 action/requester snapshot/result JSON 记录格式。

**Produces:** 可跨 API 进程重启读取的 `PostgresApprovalStore`；`memory` 只用于 CI/本地体验，`postgres` 是 P1 参考案例和发布前验收要求的审批存储。

- [ ] **Step 1: 写出持久化恢复失败测试**

```python
import os
from datetime import UTC, datetime, timedelta

@pytest.mark.asyncio
async def test_postgres_store_recovers_expired_execution_after_new_instance() -> None:
    dsn = os.environ["AGENTBRIDGE_TEST_PG_DSN"]
    t0 = datetime(2026, 7, 30, tzinfo=UTC)
    record = {
        "tenant_id": "acme",
        "route": "example",
        "run_id": "r1",
        "thread_id": "t1",
        "storage_key": "acme::t1",
        "sequence": 1,
        "action": {"type": "example.write_v1", "payload": {"value": 1}},
        "requester_context": {"user_id": "u", "tenant_id": "acme"},
    }
    first = PostgresApprovalStore(dsn)
    approval_id = await first.create(record)
    await first.decide(approval_id, tenant_id="acme", decision="approve")
    await first.claim_execution(approval_id, tenant_id="acme", now=t0, lease_seconds=1)
    await first.close()  # simulate process exit after database commit, before mark_succeeded

    second = PostgresApprovalStore(dsn)
    recovered = await second.recover_expired_execution(
        approval_id, tenant_id="acme", now=t0 + timedelta(seconds=2)
    )
    assert recovered["status"] == "retryable_failed"
    assert await second.claim_execution(approval_id, tenant_id="acme", now=t0 + timedelta(seconds=2), lease_seconds=1)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest apps/api/tests/test_postgres_approval_store.py::test_postgres_store_recovers_expired_execution_after_new_instance -v`

Expected: FAIL；迁移或 `PostgresApprovalStore` 不存在。未设置 `AGENTBRIDGE_TEST_PG_DSN` 时按既有 Postgres 集成测试策略 skip。

- [ ] **Step 3: 创建通用审批 schema 与 adapter**

`004_approval_execution.sql` 创建仅平台通用的 `approval_records`：`approval_id` 主键、`tenant_id`、route/run/thread/storage key、审批序号、status/decision/reason、`action JSONB`、`requester_context JSONB`、`result JSONB`、`result_delivery_error`、`execution_started_at`、`execution_lease_expires_at`、created/updated timestamps；为 `(tenant_id, approval_id)`、`(tenant_id, status)` 建索引。不得出现工单、台账、业务权限或 route 名。

`PostgresApprovalStore` 用 asyncpg 参数化 SQL 实现 Task 3 的全部 ApprovalStore 方法。`claim_execution` 使用一条带 `status IN ('approved_pending_execution', 'retryable_failed')` 条件的 `UPDATE ... RETURNING` 写入租约；`recover_expired_execution` 使用一条带 `status = 'executing' AND execution_lease_expires_at <= $now` 条件的 `UPDATE ... RETURNING`。所有 JSONB 只序列化已定义的通用 envelope/snapshot/result；tenant 条件在每条查询与更新中必填。

在 `Settings` 增加 `approval_store_backend: str = Field(default="memory", validation_alias="APPROVAL_STORE_BACKEND")` 与 `approval_execution_lease_seconds: float = Field(default=60.0, validation_alias="APPROVAL_EXECUTION_LEASE_SECONDS")`。允许值仅 `memory`、`postgres`，非法值由 Task 6 的工厂抛出明确 `ValueError`；`postgres` 要求 PostgreSQL 和 `004_approval_execution.sql` 已应用。迁移 README 记录两份新 migration 的顺序和这一前置条件。

- [ ] **Step 4: 增加 Postgres 与 Memory 语义一致性测试**

对 Postgres 覆盖跨租户不可读、两个并发 claim 仅一个成功、未到期租约不可恢复、到期后恢复、进程重建实例仍有同一 action/result。对 Memory 使用相同状态转移矩阵；两个实现都不得将 `succeeded` 重新变为可执行。

- [ ] **Step 5: 运行持久化审批测试**

Run: `python -m pytest packages/core/tests/application/test_approval_execution.py apps/api/tests/test_postgres_approval_store.py -v`

Expected: Memory 测试通过；未设 `AGENTBRIDGE_TEST_PG_DSN` 的 Postgres 测试 skip，设定后全部通过。

- [ ] **Step 6: 提交**

Run: `git add apps/api/migrations/004_approval_execution.sql apps/api/adapters/postgres_approval_store.py apps/api/config/settings.py apps/api/migrations/README.md apps/api/tests/test_postgres_approval_store.py; git commit -m "feat: persist approval execution state"`

### Task 5: Lifecycle 持久化 action、复检并执行恢复动作

**Files:**
- Modify: `packages/core/src/agentbridge_core/application/run_lifecycle.py:45-82,577-773`
- Modify: `packages/core/tests/application/test_approval_gate.py`
- Test: `packages/core/tests/application/test_approval_execution.py`

**Consumes:** Task 3 的 ApprovalStore 状态方法、Task 4 的执行租约与 ApprovalResumeExecutor；既有 `_emit` 的 append-before-emit 语义。

**Produces:** action envelope、route/run/thread/tenant/审批序号与安全请求人快照在审批前写入 Store；批准后重新取得线程锁、按请求人上下文复检并执行；无 action 审批保持兼容。

- [ ] **Step 1: 写出 executor 调用失败测试**

```python
assert executor.calls == [("echo", {"type": "example.write_v1", "payload": {"x": 1}}, approval_id)]
assert any(event["type"] == "x.example.created" for event in sink.events)
```

测试以 ApprovalAwareRuntime fragment data 增加 action，调用 `finalize_approval` 时传 requester 与拥有 `approval:decide` 的 approver context。

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest packages/core/tests/application/test_approval_execution.py::test_approved_action_executes_once -v`

Expected: FAIL，RunLifecycle 尚不接受 executor/context 参数。

- [ ] **Step 3: 按边界修改 Lifecycle**

1. 构造函数增加 `approval_executor: ApprovalResumeExecutor | None = None`、`approval_execution_lease_seconds: float = 60.0` 和可注入 UTC clock；`finalize_approval` 增加 `approver_ctx: RunContext | None = None`。HTTP approve 必须提供该上下文，内部 timeout 只传 deny 与 `reason="timeout"`。
2. `_pause_for_approval` 接收 `RunContext`，在发出 `x.bridge.approval_required` 前保存 route、run_id、thread_id、tenant_id、审批序号、完整 action 和安全请求人快照；快照只保存 user_id、tenant_id、roles、permissions、预算与 policy_bundle_version，绝不保存 metadata 内的客户端或 token map。
3. action 必须有非空 type 和 dict payload；非法 action 发 `error(code="invalid_approval_action")`，且不建审批记录。已持久化 action 是唯一可执行草稿，批准后不得调用模型或重建 payload。
4. 对 pending 记录先 `decide(decision=..., reason=reason)`；approve 随后重获记录对应 thread 的锁，校验当前 approver 的 `approval:decide`，调用 `resource_for`，以存储 requester context 对该 resource 执行 `policy.decide(action="invoke_tool")`。Policy deny、无 handler、route/action 不匹配或 action schema 不支持时调用 `mark_execution_denied(reason=...)`，再以 `approval_resolved(skipped=true)` 和 done 终端返回，均不得 claim 或写业务表。其余情况记录复检结论后才 `claim_execution(now=clock(), lease_seconds=...)`。对已批准的 `retryable_failed` 记录不要求第二次人工审批，直接按原已持久化 action 重试；若记录仍是未到期 `executing`，返回其 in-progress 状态而不调用 handler；若租约到期，先 `recover_expired_execution(now=clock())` 再 claim。拒绝、超时均不得 claim 成功或写业务表。
5. approve 的事件顺序固定为：executor 业务事务成功 → `mark_succeeded(result={"fragments": [...]})` → `x.bridge.approval_resolved(decision="approve", skipped=false)` → executor fragments（含 `x.work_order_ops.work_order_created`）→ `done`。不得在 executor 前发 approve 成功事件或 `tool_result`。deny/timeout 的顺序保持 `approval_resolved` → `done`，且没有 executor。
6. executor 异常时 `mark_retryable_failed` 并发 `error(code="approval_execution_failed")` 与 error 终端，不伪造 `tool_result`。业务已成功后的任一 EventLog append 失败时调用 `mark_result_delivery_failed`，但保留 succeeded；error data 写 `business_completed=true`。审批查询/审计必须保留已持久化 result 与 `result_delivery_error`，不得二次执行。
7. 不含 action 的既有 demo 保持原 approve/deny 事件语义。

- [ ] **Step 4: 增加失败路径测试**

覆盖 action/route/请求人快照/审批序号被持久化、无 handler、route/action 错配、Policy deny、approver 无权限、未到期执行不重入、租约到期后重试、executor 抛错、EventLog append 失败后再次 finalize 不重执行；断言 `approval_resolved`/`error`/终端事件、`result_delivery_error`、成功扩展事件和 executor 调用次数均符合幂等语义，并通过 `MemoryAuditLogger` 断言复检结果被审计且 detail 不含 metadata/token。

- [ ] **Step 5: 运行 core 审批测试**

Run: `python -m pytest packages/core/tests/application/test_approval_gate.py packages/core/tests/application/test_approval_execution.py packages/core/tests/application/test_event_log_emit_order.py -v`

Expected: PASS。

- [ ] **Step 6: 提交**

Run: `git add packages/core/src/agentbridge_core/application/run_lifecycle.py packages/core/tests/application/test_approval_gate.py packages/core/tests/application/test_approval_execution.py; git commit -m "feat: execute approved actions through lifecycle"`

### Task 6: API action registry 与审批接线

**Files:**
- Create: `apps/api/adapters/approval_action_registry.py`
- Modify: `apps/api/lifespan.py`
- Modify: `apps/api/routes/approvals.py`
- Test: `apps/api/tests/test_approval_action_registry.py`
- Test: `apps/api/tests/test_approvals_api.py`

**Consumes:** Task 3 executor Port、Task 4 durable store 选择规则和 Task 5 Lifecycle 参数。

**Produces:** 只由 lifespan 构造并注入 Lifecycle 的通用 registry；HTTP 路由传入审批人上下文。Task 7 才将具体 domain handler 绑定到 registry。

- [ ] **Step 1: 写出 route/action 错配失败测试**

```python
def test_registry_rejects_action_registered_for_another_route() -> None:
    registry = ApprovalActionRegistry()
    registry.register("route_a", "a.write_v1", handler, {"name": "write"})
    with pytest.raises(ValueError, match="no approval action"):
        registry.resource_for(route="route_b", action={"type": "a.write_v1", "payload": {}})
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest apps/api/tests/test_approval_action_registry.py::test_registry_rejects_action_registered_for_another_route -v`

Expected: FAIL，registry 文件不存在。

- [ ] **Step 3: 实现 registry 和宿主组装**

实现 `register(route, action_type, handler: ApprovalActionHandler, resource)`、`resource_for`、`execute`；重复键、payload 非 dict、未知 action、非 `OutboundFragment` 返回值都抛 `ValueError`。registry 只持有 Protocol handler，不 import 任意 domain。

在 `lifespan.py` 新增 `_build_approval_store(settings)`：`memory` 返回 `MemoryApprovalStore`，`postgres` 返回 `PostgresApprovalStore(_resolve_postgres_dsn(settings))`，其它值抛 `ValueError("unsupported approval store backend")`。lifespan 负责关闭支持 `close()` 的 store，并将 `settings.approval_execution_lease_seconds` 注入 Lifecycle。

lifespan 创建空 registry，将其作为 `approval_executor` 注入 Lifecycle，并把 registry 放 `app.state.approval_actions` 仅供测试/诊断，HTTP 不直接调用。本任务不得 import 或注册 `work_order_ops`；registry 的 handler 仅由本任务测试提供的通用 callable 证明接口可用。Task 7 再将 domain bootstrap、事务 Port 和测试注入一起接到该 registry。

`resolve_approval` 保留路由层 `approval:decide` 检查，并把完整 ctx 作为 approver context 传 Lifecycle；timeout 仅允许 deny，无 approver context。

- [ ] **Step 4: 运行 API 审批测试**

Run: `python -m pytest apps/api/tests/test_approvals_api.py apps/api/tests/test_approval_action_registry.py -v`

Expected: PASS；`demo_approval_write` 的 legacy approve 仍通过。

- [ ] **Step 5: 提交**

Run: `git add apps/api/adapters/approval_action_registry.py apps/api/lifespan.py apps/api/routes/approvals.py apps/api/tests/test_approvals_api.py apps/api/tests/test_approval_action_registry.py; git commit -m "feat: wire approval action registry"`

### Task 7: 脱敏数据与工单运营 domain

**Files:**
- Create: `apps/api/migrations/005_work_order_ops.sql`
- Create: `apps/api/domains/work_order_ops/__init__.py`
- Create: `apps/api/domains/work_order_ops/state.py`
- Create: `apps/api/domains/work_order_ops/tools.py`
- Create: `apps/api/domains/work_order_ops/graph.py`
- Create: `apps/api/domains/work_order_ops/approval.py`
- Create: `apps/api/domains/work_order_ops/bootstrap.py`
- Modify: `apps/api/domains/bootstrap.py`
- Modify: `apps/api/lifespan.py`
- Test: `apps/api/tests/test_work_order_ops.py`

**Consumes:** Task 1 transaction Port、Task 4 持久化审批语义、Task 6 注入的 handler registry、现有 Retriever 与 fragment protocol。

**Produces:** `route="work_order_ops"`，产生 list/chart/ledger preview/created/citation 的可复现 domain。

- [ ] **Step 1: 写出真实运行时的查询、图表与草稿事件失败测试**

```python
assert "x.work_order_ops.list" in types
assert "x.work_order_ops.chart" in types
chart = next(e for e in events if e["type"] == "x.work_order_ops.chart")
assert chart["data"]["schema_version"] == 1
assert chart["data"]["chart_type"] == "bar"
assert "x.bridge.citation" in types
```

测试文件定义本地 `work_order_client` fixture，不使用 `conftest.py` 的默认 `client`：在 `create_test_app()` 前设置 `AGENTBRIDGE_FAKE_RUNTIME=0`，创建 `FakeDataSource` 并 seed 两个 tenant，再在 `TestClient` 启动前设置 `app.state.bootstrap_data_source = fake_data_source`。启动后将已 seed 的 `FakeRetriever` 设置到 `app.state.retriever`。断言运行的是 `LangGraphRuntime`，而非 `ApiFakeRuntime`。对创建查询断言 `ledger_preview` 的 `draft_id/work_order/ledger/approval_required=true`、`approval_required` 的 tool/timeout/action type/payload 均符合 schema，且尚无新 approval_id；列表断言 columns/rows/total/truncated 且 rows 不含敏感字段，图表分别覆盖 `bar`、`line`、`pie` 的 schema v1 和空结果零值。

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest apps/api/tests/test_work_order_ops.py -v`

Expected: FAIL，`unknown route: work_order_ops`。

- [ ] **Step 3: 创建迁移、草稿模型和批准 handler**

`005_work_order_ops.sql` 创建 `work_orders(id, tenant_id, approval_id, title, status, priority, assignee_id, created_at, updated_at)`、`assignees(id, tenant_id, name, team, active, specialties)`、`ledgers(id, tenant_id, approval_id, work_order_id, summary, created_at)`；全部 `tenant_id NOT NULL`，work_orders/ledgers 都有 `approval_id TEXT NOT NULL` 和各自的 `UNIQUE (tenant_id, approval_id)`。迁移使用幂等 DDL 和固定的合成 ID；种子含两个租户、脱敏标题与 active assignee，禁止真实姓名、电话、地址和业务编号。

在 `approval.py` 定义：

```python
class CreateWorkOrderDraft(BaseModel):
    draft_id: constr(min_length=1, max_length=64)
    title: constr(min_length=3, max_length=120)
    priority: Literal["low", "medium", "high"]
    assignee_id: constr(min_length=1, max_length=64)
    ledger_summary: constr(min_length=3, max_length=500)
```

实现 `make_create_work_order_handler(data_source: TransactionalDataSource) -> ApprovalActionHandler`。handler 对 action payload 先执行 `CreateWorkOrderDraft.model_validate`；`prepare_work_order_draft` 发出预览和审批 action 前也必须对同一模型校验。handler 在闭包中的 `data_source.transaction` 内，先以 `(tenant_id, approval_id)` 分别查询 work_orders 与 ledgers：若两条记录均存在，则用其中 `id`、assignee/status 重建原 `x.work_order_ops.work_order_created` payload；若只存在一条则抛出一致性错误并回滚；若均不存在，才在同一事务中复验 assignee 的 tenant/active 并插入工单与台账。事务成功后返回 `OutboundFragment(type="x.work_order_ops.work_order_created", data={"schema_version": 1, "work_order_id": work_order_id, "ledger_id": ledger_id, "assignee_id": draft.assignee_id, "status": "open"})`。不得从 `requester_ctx.metadata` 取数据源；`tenant_id` 只取 `requester_ctx.tenant_id`，不得取 action payload。

- [ ] **Step 4: 实现只读工具、图和注册**

定义 `list_work_orders`、`work_order_statistics`、`search_work_order_knowledge`、`prepare_work_order_draft`；前三者分别以 `attach_tool_meta(required_permissions=["workorder:read"])`、`attach_tool_meta(required_permissions=["knowledge:read"])` 标记，`prepare_work_order_draft` 必须使用 `attach_tool_meta(required_permissions_all=["workorder:create", "workorder:assign"])`。审批 registry 为 `work_order_ops.create_v1` 登记相同 `required_permissions_all` resource，确保恢复时也是 all-of 检查。工具调用 `get_run_context(config)`，用参数化 SQL 和 `ctx.tenant_id`。为了让 Task 1 的 FakeDataSource 与 Postgres 执行同一业务逻辑，查询只使用按 tenant_id 的单表 `SELECT`，在 Python 中关联 assignee、计算 chart 和截断列表；不得依赖 SQL JOIN、GROUP BY 或数据库特有 UPSERT。图按关键词调用工具，并将 list/chart/ledger_preview 写入 `OUTBOUND_EXTENSIONS_KEY`，不直接发 SSE。`prepare_work_order_draft` 的 action 固定为 `{"type": "work_order_ops.create_v1", "payload": CreateWorkOrderDraft(...).model_dump()}`，不得让模型在批准后重新生成。

在本任务更新 `register_all(..., *, approval_actions: ApprovalActionRegistrar, data_source: TransactionalDataSource)`：`ApprovalActionRegistrar` 来自 core Port，domain/bootstrap 不得 import `ApprovalActionRegistry` adapter。既有 domain 仍以原三个参数注册，只有 `work_order_ops.register` 接收这两个关键字参数。将 lifespan 中现有 data source 构造移动到 `register_all` 之前，并替换为 `data_source = getattr(app.state, "bootstrap_data_source", None) or _build_data_source(settings)`；随后以同一对象调用 `register_all(graphs, tools, input_builders, approval_actions=registry, data_source=data_source)`。`work_order_ops.register` 以这个 `data_source` 调用 `make_create_work_order_handler(data_source)` 并把返回值登记为 `("work_order_ops", "work_order_ops.create_v1")`。这个 closure 是审批写入路径唯一的数据源来源；查询工具仍从实时 `RunContext.metadata["data_source"]` 取 Port。测试在 `TestClient` 启动前设置 `app.state.bootstrap_data_source = FakeDataSource()`，从而使查询与审批 handler 使用同一实例；生产没有该测试钩子时只走 `_build_data_source`。

- [ ] **Step 5: 增加批准后的端到端测试**

请求创建→取得 approval_id→以审批人权限 POST `/approvals/{id}`→断言 `approval_id`、持久化 action 与两张表的写入字段一致；重复 approve、并发 approve 与“业务提交后、mark_succeeded 前”的重试均不新增行且产生完全相同的创建 payload。覆盖审批前、deny、timeout、请求人 Policy 复检失败、处理人失效、草稿无效、跨租户、事务第二次写入失败时均为零写入。缺少 `workorder:read`、`knowledge:read`、`workorder:create` 或 `workorder:assign` 时分别断言工具不可见并在执行期拒绝；跨租户不能读取工单、处理人、台账或知识 citation。对旧客户端模拟忽略 `x.work_order_ops.*`，断言仍收到 `start`、稳定事件和 `done`。

新增标记为 `AGENTBRIDGE_TEST_PG_DSN` 的重启恢复集成测试：在测试库按顺序应用 `004_approval_execution.sql` 和 `005_work_order_ops.sql`；第一实例以 `APPROVAL_STORE_BACKEND=postgres` 执行 handler 的事务写入后故意不调用 `mark_succeeded` 并关闭；第二实例在执行租约到期后恢复同一 approval，断言只得到原工单/台账、重新持久化的 created payload 与第一实例可重建结果完全一致。未设 DSN 时 skip；此测试是“崩溃可恢复”验收，不能以 Memory 测试代替。

新增 external RAG 故障测试：设置 `KNOWLEDGE_BACKEND=external`、`KB_EXTERNAL_FAILURE_POLICY=fail_run`，用 `httpx.MockTransport` 返回超时或 503；断言请求得到稳定 `error`、不发 citation，且错误文本标识“知识暂不可用”。另以 200/`hits: []` 断言业务结果明确为“知识未命中”。这两条断言禁止将后端故障伪装为普通空结果。

- [ ] **Step 6: 运行 domain 测试**

Run: `python -m pytest apps/api/tests/test_work_order_ops.py apps/api/tests/test_demo_readonly_policy.py apps/api/tests/test_demo_rag.py -v`

Expected: PASS。

- [ ] **Step 7: 提交**

Run: `git add apps/api/migrations/005_work_order_ops.sql apps/api/domains/work_order_ops apps/api/domains/bootstrap.py apps/api/lifespan.py apps/api/tests/test_work_order_ops.py; git commit -m "feat: add work order operations reference domain"`

### Task 8: 文档、契约样例与全量验证

**Files:**
- Create: `apps/api/domains/work_order_ops/README.md`
- Modify: `docs/contracts.md`
- Modify: `docs/knowledge-base.md`
- Modify: `docs/add-a-domain.md`
- Test: `apps/api/tests/test_work_order_ops.py`

**Consumes:** Tasks 1–7 的实际事件 payload、迁移与权限。

**Produces:** 集成方可配置脱敏数据、调用 route 并渲染结构化事件；业务作者知道审批 action 的新约束。

- [ ] **Step 1: 写出会失败的文档存在性检查**

```powershell
if (-not (Test-Path 'apps/api/domains/work_order_ops/README.md')) { throw 'missing reference doc' }
```

- [ ] **Step 2: 运行检查并确认失败**

Run: Step 1 的 PowerShell 命令。

Expected: `missing reference doc`。

- [ ] **Step 3: 编写文档和 SSE 样例**

domain README 写迁移命令、Fake/PG/RAG 配置、四个示例 query、所需 permissions、审批 POST 与预期 `x.work_order_ops.*` 事件。它必须明确 P1 真实运行和重启恢复验收需要 `APPROVAL_STORE_BACKEND=postgres`、已应用 `004_approval_execution.sql`/`005_work_order_ops.sql`，并将 `memory` 标为仅 CI/本地体验。README 逐项给出 list/chart/ledger preview/created/action payload 的 schema v1 样例，并说明 `bar`/`line`/`pie` 不受支持时客户端退化为标题、类别与序列值列表。`contracts.md` 增加非规范性链接，说明扩展 payload 以 domain README 为准、消费者按 sequence 去重排序且旧客户端可忽略未知 `x.*` 事件。`add-a-domain.md` 增加 `(route, action.type)` 注册、类型校验和 approval_id 幂等规则；`knowledge-base.md` 链接该 RAG 参考案例，并说明 external 后端故障/超时在 P1 验收配置 `KB_EXTERNAL_FAILURE_POLICY=fail_run` 下进入可识别 error 路径，200 空命中才表示知识未命中。

- [ ] **Step 4: 运行全量门禁**

Run: `python -m pytest packages/core/tests apps/api/tests -q; python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"; python scripts/import_scan_core.py; python scripts/import_scan_rag_engines.py`

Expected: 测试、import-linter 和两项扫描全部通过。

- [ ] **Step 5: 执行手工 RAG 验收**

Run: `docker compose --profile rag up -d; pip install -e "apps/api[rag]"; psql "$env:PG_DSN" -f apps/api/migrations/004_approval_execution.sql; psql "$env:PG_DSN" -f apps/api/migrations/005_work_order_ops.sql; python scripts/ingest_demo_rag.py`

以 `APPROVAL_STORE_BACKEND=postgres`、真实 `langchain_pg` 配置启动 API，验证同 tenant 收到 citation，其他 tenant 无结果，并以 `KB_EXTERNAL_FAILURE_POLICY=fail_run` 对 external 503 验证“知识暂不可用”。若缺 Docker、embedding 服务、psql 或 PG，记录为 P2 外部环境阻塞，不把 Fake 测试当真实验收。

- [ ] **Step 6: 提交**

Run: `git add apps/api/domains/work_order_ops/README.md docs/contracts.md docs/knowledge-base.md docs/add-a-domain.md; git commit -m "docs: document work order reference integration"`

## 全量验收

- [ ] **Step 1: 检查提交边界**

Run: `git status --short; git log --oneline -6`

Expected: 无未追踪实现文件；提交按事务 Port、审批状态机、Lifecycle、API 组装、domain、文档分组。

- [ ] **Step 2: 复跑发布前门禁**

Run: `python -m pytest packages/core/tests apps/api/tests -q; python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"; python scripts/import_scan_core.py; python scripts/import_scan_rag_engines.py`

Expected: 全部通过；若缺 dev 依赖，按 README 安装并记录命令输出，不跳过门禁。

## Spec 对齐自检

| 已批准设计要求 | 对应计划任务与可验证证据 |
|---|---|
| 全新 `work_order_ops` domain、脱敏种子、查询/RAG/列表/图表/台账预览 | Task 7 迁移、工具、图与真实 LangGraph API 测试；Task 8 运行说明 |
| 事务 Port、Port/Adapter 分层、core 无业务名、domain 不推 SSE | Task 1 的 Fake/Noop/Postgres 事务；Task 2–6 的通用权限、审批 Port/registry；Global Constraints 与 import 门禁 |
| action envelope、请求人安全快照、审批人和请求人双重复检 | Task 3 的 Store/Port；Task 5 的暂停持久化、线程锁、Policy/Audit 测试；Task 6 的 approver context 路由接线 |
| `pending → approved_pending_execution → executing → succeeded/retryable_failed`、拒绝/超时零写入 | Task 3 状态转换测试；Task 4 持久化租约；Task 5 终端语义；Task 7 的 deny/timeout/失败写入断言 |
| `approval_id` 幂等、工单与台账单事务、提交后崩溃可恢复 | Task 1 事务回滚；Task 4 跨实例 record 恢复；Task 7 handler 的既有记录重建与 PG 重启集成测试 |
| 稳定 SSE、`x.work_order_ops.*` schema v1、citation、旧客户端兼容 | Task 5 发射顺序与投递失败处理；Task 7 payload/旧客户端测试；Task 8 契约样例和图表降级说明 |
| 租户隔离、工具列表过滤与调用期复检、处理人有效性 | Task 2 all-of Policy；Task 7 的工具 meta、SQL tenant 条件、跨租户/权限/处理人失效测试 |
| EventLog 失败不回放业务、可查询/审计投递失败 | Task 3 `mark_result_delivery_failed`；Task 5 result 持久化与 MemoryAuditLogger 测试 |
| 真实 `langchain_pg` 与 external 检索手工验收 | Task 8 的真实 RAG 验收，明确 Fake 不可代替 |

自检结论：设计第 1–7 节均有实现任务与可观察验收证据；P1 不包含该设计明确延后到 P2 的同库 outbox、生产故障演练、备份恢复和双实例验证。它们不应被误报为 P1 完成条件。
