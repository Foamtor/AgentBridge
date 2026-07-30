# P1 工单运营助手黄金案例 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 `work_order_ops` 参考 domain：基于脱敏数据完成工单查询、RAG 引用、结构化列表/图表/台账预览，以及经人工审批后幂等地创建工单与台账。

**Architecture:** core 增加不含业务名的事务 Port、审批执行状态机和审批恢复 executor Port；API 宿主在 `lifespan.py` 组装 registry 与 Postgres/Fake 实现；domain 只登记 `(route, action.type)` handler 并通过注入 Port 读写。业务结果经 `OutboundFragment` 和 `OUTBOUND_EXTENSIONS_KEY` 进入既有 EventLog-before-SSE 生命周期。

**Tech Stack:** Python 3.12+, FastAPI, LangGraph, Pydantic v2, asyncpg, PostgreSQL, LangChain Core, pytest/pytest-asyncio。

## Global Constraints

- `agentbridge_core.application` 不 import adapters；core 源码不得出现 `work_order_ops`、工单、表名或业务权限字符串。
- domain 不创建 adapter、不 import adapter 实现、不持有 `EventSink`；扩展事件只能经 `OUTBOUND_EXTENSIONS_KEY` 输出。
- adapter 与 registry 实例只在 `apps/api/lifespan.py` 创建并注入。
- 无权限工具不进模型列表；执行与审批恢复时都必须再次 `Policy.decide`。
- 数据库 `tenant_id` 只来自 `RunContext` 或审批记录，不能来自模型 payload。
- `approval_id` 是业务写入幂等键；`work_orders` 和 `ledgers` 必须在单一事务中写入。
- 稳定 SSE 类型不变；新增事件仅为 `x.work_order_ops.*`，每个 payload 包含 `schema_version: 1`。

---

## 文件结构

- Modify: `packages/core/src/agentbridge_core/ports/data_source.py` — 事务协议。
- Modify: `packages/core/src/agentbridge_core/adapters/{fake_data_source,noop_data_source}.py`、`apps/api/adapters/postgres_data_source.py` — 事务实现。
- Create: `packages/core/src/agentbridge_core/ports/approval_resume.py` — 通用 action executor Port。
- Modify: `packages/core/src/agentbridge_core/ports/approval.py`、`adapters/memory_approval_store.py`、`application/run_lifecycle.py` — 审批状态、恢复执行。
- Create: `apps/api/adapters/approval_action_registry.py` — `(route, action.type)` registry。
- Modify: `apps/api/lifespan.py`、`apps/api/routes/approvals.py`、`apps/api/domains/bootstrap.py` — 宿主接线。
- Create: `apps/api/domains/work_order_ops/{__init__,state,tools,graph,approval,bootstrap,README}.py` — 黄金 domain。
- Create: `apps/api/migrations/004_work_order_ops.sql` — 脱敏表、幂等约束和种子。
- Create: `packages/core/tests/application/test_approval_execution.py`、`apps/api/tests/test_work_order_ops.py`、`apps/api/tests/test_approval_action_registry.py`。
- Modify: `packages/core/tests/adapters/test_fake_data_source.py`、`apps/api/tests/test_postgres_data_source.py`、`packages/core/tests/application/test_approval_gate.py`、`docs/contracts.md`、`docs/knowledge-base.md`、`docs/add-a-domain.md`。

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

### Task 2: 审批 action 状态机与恢复 executor Port

**Files:**
- Create: `packages/core/src/agentbridge_core/ports/approval_resume.py`
- Modify: `packages/core/src/agentbridge_core/ports/approval.py`
- Modify: `packages/core/src/agentbridge_core/adapters/memory_approval_store.py`
- Test: `packages/core/tests/application/test_approval_execution.py`

**Consumes:** `RunContext`、`OutboundFragment`、MemoryApprovalStore 的租户隔离。

**Produces:** 原子 `claim_execution`、`mark_succeeded`、`mark_retryable_failed` 与 route/action 解析的 `ApprovalResumeExecutor` Protocol。

- [ ] **Step 1: 写出并发 claim 的失败测试**

```python
@pytest.mark.asyncio
async def test_approval_claim_is_single_consumer() -> None:
    store = MemoryApprovalStore()
    aid = await store.create({"tenant_id": "acme", "status": "approved_pending_execution"})
    first, second = await asyncio.gather(store.claim_execution(aid, tenant_id="acme"), store.claim_execution(aid, tenant_id="acme"))
    assert sum(item is not None for item in (first, second)) == 1
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest packages/core/tests/application/test_approval_execution.py::test_approval_claim_is_single_consumer -v`

Expected: FAIL，`claim_execution` 未定义。

- [ ] **Step 3: 定义 Port 与内存状态机**

在 `approval.py` 扩展 Protocol，方法签名为：

```python
async def decide(self, approval_id: str, *, tenant_id: str, decision: str) -> dict[str, Any] | None:
    pass
async def claim_execution(self, approval_id: str, *, tenant_id: str) -> dict[str, Any] | None:
    pass
async def mark_succeeded(self, approval_id: str, *, tenant_id: str, result: dict[str, Any]) -> dict[str, Any] | None:
    pass
async def mark_retryable_failed(self, approval_id: str, *, tenant_id: str, error: str) -> dict[str, Any] | None:
    pass
```

approve 将 pending 改为 `approved_pending_execution`；deny/timeout 改为 `denied`。claim 仅允许 `approved_pending_execution`、`retryable_failed`；成功改 `executing`。所有检查与修改必须在 MemoryApprovalStore 同一 `asyncio.Lock` 内。

在新 `approval_resume.py` 定义：

```python
class ApprovalResumeExecutor(Protocol):
    def resource_for(self, *, route: str, action: dict[str, Any]) -> dict[str, Any]:
        pass
    async def execute(self, *, route: str, action: dict[str, Any], requester_ctx: RunContext, approval_id: str) -> list[OutboundFragment]:
        pass
```

- [ ] **Step 4: 增加状态转移测试**

覆盖 approve→claim→succeeded、执行失败→retryable_failed→再次 claim、deny 不可 claim、跨租户返回 None；每项断言 result 或 error 被持久化。

- [ ] **Step 5: 运行相关测试**

Run: `python -m pytest packages/core/tests/application/test_approval_execution.py -v`

Expected: PASS。

- [ ] **Step 6: 提交**

Run: `git add packages/core/src/agentbridge_core/ports/approval.py packages/core/src/agentbridge_core/ports/approval_resume.py packages/core/src/agentbridge_core/adapters/memory_approval_store.py packages/core/tests/application/test_approval_execution.py; git commit -m "feat: add approval execution state machine"`

### Task 3: Lifecycle 持久化 action、复检并执行恢复动作

**Files:**
- Modify: `packages/core/src/agentbridge_core/application/run_lifecycle.py:45-82,577-773`
- Modify: `packages/core/tests/application/test_approval_gate.py`
- Test: `packages/core/tests/application/test_approval_execution.py`

**Consumes:** Task 2 的 ApprovalStore 状态方法和 ApprovalResumeExecutor；既有 `_emit` 的 append-before-emit 语义。

**Produces:** action envelope 在审批前写入 Store；批准后按请求人上下文复检并执行；无 action 审批保持兼容。

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

1. 构造函数增加 `approval_executor: ApprovalResumeExecutor | None = None`。
2. `_pause_for_approval` 接收 RunContext；只保存 user_id、tenant_id、roles、permissions、预算与 policy_bundle_version，绝不保存 metadata 内的客户端或 token map。
3. action 必须有非空 type 和 dict payload；非法 action 发 `error(code="invalid_approval_action")`，且不建审批记录。
4. approve 时校验 approver 权限，调用 `resource_for`，对存储 requester context 执行 `policy.decide(action="invoke_tool")`，然后 claim。
5. executor 成功后先 `mark_succeeded(result=fragment.data)`，再把 fragments 经 `_envelope_from_fragment` 与 `_emit` 输出；失败时 mark retryable 并发 `error(code="approval_execution_failed")`。
6. 业务已成功但 EventLog append 失败时保留 succeeded，error data 写 `business_completed=true`，不得二次执行。
7. 不含 action 的既有 demo 保持原 approve/deny 事件语义。

- [ ] **Step 4: 增加失败路径测试**

覆盖无 handler、route/action 错配、Policy deny、executor 抛错、EventLog append 失败后再次 finalize 不重执行；断言成功扩展事件和 executor 调用次数均符合幂等语义。

- [ ] **Step 5: 运行 core 审批测试**

Run: `python -m pytest packages/core/tests/application/test_approval_gate.py packages/core/tests/application/test_approval_execution.py packages/core/tests/application/test_event_log_emit_order.py -v`

Expected: PASS。

- [ ] **Step 6: 提交**

Run: `git add packages/core/src/agentbridge_core/application/run_lifecycle.py packages/core/tests/application/test_approval_gate.py packages/core/tests/application/test_approval_execution.py; git commit -m "feat: execute approved actions through lifecycle"`

### Task 4: API action registry 与审批接线

**Files:**
- Create: `apps/api/adapters/approval_action_registry.py`
- Modify: `apps/api/lifespan.py`
- Modify: `apps/api/domains/bootstrap.py`
- Modify: `apps/api/routes/approvals.py`
- Test: `apps/api/tests/test_approval_action_registry.py`
- Test: `apps/api/tests/test_approvals_api.py`

**Consumes:** Task 2 executor Port 和 Task 3 Lifecycle 参数。

**Produces:** 只由 lifespan 构造的 registry；domain 可声明 handler；HTTP 路由传入审批人上下文。

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

实现 `register(route, action_type, handler, resource)`、`resource_for`、`execute`；重复键、payload 非 dict、未知 action、非 OutboundFragment 返回值都抛 ValueError。lifespan 创建 registry，调用 `register_all(graphs, tools, input_builders, approval_actions=registry)`，并作为 `approval_executor` 注入 Lifecycle。将 registry 放 `app.state.approval_actions` 仅作测试/诊断，HTTP 不直接调用。

`resolve_approval` 保留路由层 `approval:decide` 检查，并把完整 ctx 作为 approver context 传 Lifecycle；timeout 仅允许 deny，无 approver context。

- [ ] **Step 4: 运行 API 审批测试**

Run: `python -m pytest apps/api/tests/test_approvals_api.py apps/api/tests/test_approval_action_registry.py -v`

Expected: PASS；`demo_approval_write` 的 legacy approve 仍通过。

- [ ] **Step 5: 提交**

Run: `git add apps/api/adapters/approval_action_registry.py apps/api/lifespan.py apps/api/domains/bootstrap.py apps/api/routes/approvals.py apps/api/tests/test_approvals_api.py apps/api/tests/test_approval_action_registry.py; git commit -m "feat: wire approval action registry"`

### Task 5: 脱敏数据与工单运营 domain

**Files:**
- Create: `apps/api/migrations/004_work_order_ops.sql`
- Create: `apps/api/domains/work_order_ops/__init__.py`
- Create: `apps/api/domains/work_order_ops/state.py`
- Create: `apps/api/domains/work_order_ops/tools.py`
- Create: `apps/api/domains/work_order_ops/graph.py`
- Create: `apps/api/domains/work_order_ops/approval.py`
- Create: `apps/api/domains/work_order_ops/bootstrap.py`
- Modify: `apps/api/domains/bootstrap.py`
- Test: `apps/api/tests/test_work_order_ops.py`

**Consumes:** Task 1 transaction Port、Task 4 registry、现有 Retriever 与 fragment protocol。

**Produces:** `route="work_order_ops"`，产生 list/chart/ledger preview/created/citation 的可复现 domain。

- [ ] **Step 1: 写出查询、图表与草稿事件失败测试**

```python
assert "x.work_order_ops.list" in types
assert "x.work_order_ops.chart" in types
chart = next(e for e in events if e["type"] == "x.work_order_ops.chart")
assert chart["data"]["schema_version"] == 1
assert chart["data"]["chart_type"] == "bar"
assert "x.bridge.citation" in types
```

FakeDataSource seed 两个 tenant，FakeRetriever seed SOP；对创建查询断言 `ledger_preview` 与 `approval_required` 存在，且尚无新 approval_id。

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest apps/api/tests/test_work_order_ops.py -v`

Expected: FAIL，`unknown route: work_order_ops`。

- [ ] **Step 3: 创建迁移、草稿模型和批准 handler**

迁移创建 `work_orders`、`assignees`、`ledgers`；全部 `tenant_id NOT NULL`，work_orders/ledgers 都有 `approval_id TEXT NOT NULL` 和 `UNIQUE (tenant_id, approval_id)`。种子含两个租户、脱敏标题与 active assignee，禁止真实姓名、电话、地址和业务编号。

在 `approval.py` 定义：

```python
class CreateWorkOrderDraft(BaseModel):
    title: constr(min_length=3, max_length=120)
    priority: Literal["low", "medium", "high"]
    assignee_id: constr(min_length=1, max_length=64)
    ledger_summary: constr(min_length=3, max_length=500)
```

handler 先按 approval_id 读取已有结果；不存在时调用 `data_source.transaction`，事务内复验 assignee 的 tenant/active，插入工单与台账，返回 `OutboundFragment(type="x.work_order_ops.work_order_created", data={"schema_version": 1, "work_order_id": work_order_id, "ledger_id": ledger_id, "assignee_id": draft.assignee_id, "status": "open"})`。

- [ ] **Step 4: 实现只读工具、图和注册**

定义 `list_work_orders`、`work_order_statistics`、`search_work_order_knowledge`、`prepare_work_order_draft`；以 `attach_tool_meta` 分别标记 `workorder:read`、`knowledge:read`、`workorder:create`/`workorder:assign`。工具调用 `get_run_context(config)`，用参数化 SQL 和 `ctx.tenant_id`。图按关键词调用工具，并将 list/chart/ledger_preview 写入 `OUTBOUND_EXTENSIONS_KEY`，不直接发 SSE。bootstrap 注册 graph/tools/input builder 和 `("work_order_ops", "work_order_ops.create_v1")` handler/resource。

- [ ] **Step 5: 增加批准后的端到端测试**

请求创建→取得 approval_id→以审批人权限 POST `/approvals/{id}`→断言工单与台账均含 approval_id→重复 approve 不新增行→跨租户审批为 404 或 403。缺少 `workorder:create` 时断言工具不可见并在执行期拒绝。

- [ ] **Step 6: 运行 domain 测试**

Run: `python -m pytest apps/api/tests/test_work_order_ops.py apps/api/tests/test_demo_readonly_policy.py apps/api/tests/test_demo_rag.py -v`

Expected: PASS。

- [ ] **Step 7: 提交**

Run: `git add apps/api/migrations/004_work_order_ops.sql apps/api/domains/work_order_ops apps/api/domains/bootstrap.py apps/api/tests/test_work_order_ops.py; git commit -m "feat: add work order operations reference domain"`

### Task 6: 文档、契约样例与全量验证

**Files:**
- Create: `apps/api/domains/work_order_ops/README.md`
- Modify: `docs/contracts.md`
- Modify: `docs/knowledge-base.md`
- Modify: `docs/add-a-domain.md`
- Test: `apps/api/tests/test_work_order_ops.py`

**Consumes:** Tasks 1–5 的实际事件 payload、迁移与权限。

**Produces:** 集成方可配置脱敏数据、调用 route 并渲染结构化事件；业务作者知道审批 action 的新约束。

- [ ] **Step 1: 写出会失败的文档存在性检查**

```powershell
if (-not (Test-Path 'apps/api/domains/work_order_ops/README.md')) { throw 'missing reference doc' }
```

- [ ] **Step 2: 运行检查并确认失败**

Run: Step 1 的 PowerShell 命令。

Expected: `missing reference doc`。

- [ ] **Step 3: 编写文档和 SSE 样例**

domain README 写迁移命令、Fake/PG/RAG 配置、四个示例 query、所需 permissions、审批 POST 与预期 `x.work_order_ops.*` 事件。`contracts.md` 增加非规范性链接，说明扩展 payload 以 domain README 为准且旧客户端可忽略。`add-a-domain.md` 增加 `(route, action.type)` 注册、类型校验和 approval_id 幂等规则；`knowledge-base.md` 链接该 RAG 参考案例。

- [ ] **Step 4: 运行全量门禁**

Run: `python -m pytest packages/core/tests apps/api/tests -q; python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"; python scripts/import_scan_core.py; python scripts/import_scan_rag_engines.py`

Expected: 测试、import-linter 和两项扫描全部通过。

- [ ] **Step 5: 执行手工 RAG 验收**

Run: `docker compose --profile rag up -d; pip install -e "apps/api[rag]"; python scripts/ingest_demo_rag.py`

以真实 `langchain_pg` 配置启动 API，验证同 tenant 收到 citation，其他 tenant 无结果。若缺 Docker、embedding 服务或 PG，记录为 P2 外部环境阻塞，不把 Fake 测试当真实验收。

- [ ] **Step 6: 提交**

Run: `git add apps/api/domains/work_order_ops/README.md docs/contracts.md docs/knowledge-base.md docs/add-a-domain.md; git commit -m "docs: document work order reference integration"`

## 全量验收

- [ ] **Step 1: 检查提交边界**

Run: `git status --short; git log --oneline -6`

Expected: 无未追踪实现文件；提交按事务 Port、审批状态机、Lifecycle、API 组装、domain、文档分组。

- [ ] **Step 2: 复跑发布前门禁**

Run: `python -m pytest packages/core/tests apps/api/tests -q; python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"; python scripts/import_scan_core.py; python scripts/import_scan_rag_engines.py`

Expected: 全部通过；若缺 dev 依赖，按 README 安装并记录命令输出，不跳过门禁。
