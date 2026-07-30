# 工单运营助手黄金案例设计

> **状态：** 已修订，待用户复核
> **日期：** 2026-07-30  
> **关联发布阶段：** [P1 黄金参考实现](../../release-plan.md)  
> **定位：** 参考 RAG_Agent 的真实业务形态，全新实现为 AgentBridge domain；不迁移 RAG_Agent 的代码或产品专属工具。

## 1. 目标与边界

新增 `work_order_ops` 业务插件，展示传统系统接入 AI 的完整闭环：

1. 按租户、权限查询脱敏工单数据；
2. 结合 SOP、FAQ、分派规则等知识文档回答，并发出标准 citation；
3. 输出结构化工单列表、统计图表和台账预览；
4. 拟定工单内容和处理人后，人工审核批准才创建工单及对应台账。

首版使用仓库 migration 初始化的脱敏示例数据和知识文档。它不接入 RAG_Agent 服务、不生成 HTML/图片、不提供客户业务前端、不实现 OCR 或通用报表系统。

## 2. 架构与依赖

```text
POST /chat/stream (JSON)
  → work_order_ops domain
     ├─ TransactionalDataSource Port：工单、处理人、台账
     ├─ Retriever Port：SOP / FAQ / 分派规则
     ├─ Policy：list_tools 过滤 + invoke_tool 再鉴权
     └─ ApprovalResumeExecutor Port：创建工单前暂停，批准后恢复同一 run 的已登记动作
  → EventLog.append
  → SSE：稳定事件 + x.work_order_ops.* 结果事件
```

domain 仅从 `RunContext.metadata` 取已注入的 `data_source`、`retriever` 等 Port，不 import 或创建 adapter，也不持有 `EventSink`。适配器创建、事务实现和审批恢复执行器的组装仍只在 `apps/api/lifespan.py`。

### 2.1 P1 需要补齐的通用能力

现有 `DataSource` 只有单语句 `query` / `execute`，而现有审批完成后只写 `approval_resolved`、`tool_result` 和 `done`，不会执行原业务动作。为满足本案例的原子性与人工审核语义，P1 新增两个不含任何业务名的 Port：

| Port | 职责 | 实现与组装 |
|------|------|------------|
| `TransactionalDataSource` | 在同一连接、同一数据库事务中执行一组查询/写入；失败时回滚 | Fake 与 Postgres adapter；由 lifespan 注入 |
| `ApprovalResumeExecutor` | 在批准后根据已持久化的通用 action envelope 找到已登记的 domain handler，执行并返回 `OutboundFragment` | 由 app 侧 action registry 实现；lifespan 组装并注入 Lifecycle |

`ApprovalResumeExecutor` 不 import domain；`work_order_ops` 在注册期登记自己的 `work_order_ops.create_v1` handler。该 handler 只依赖注入的 Port。核心只认识通用 action envelope 和 executor Port，禁止出现 `work_order_ops`、工单或台账名称。

## 3. 数据与权限

示例数据至少包含：

| 实体 | 关键字段 | 用途 |
|------|----------|------|
| `work_orders` | id、tenant_id、title、status、priority、assignee_id、created_at、updated_at | 查询、统计、创建 |
| `assignees` | id、tenant_id、name、team、active、specialties | 指派校验 |
| `ledgers` | id、tenant_id、work_order_id、summary、created_at | 创建后可追溯台账 |

所有表必须按 `tenant_id` 查询与写入；值来自 `RunContext`，请求或模型参数不能覆盖。工具权限：

| 工具 | 权限 | 行为 |
|------|------|------|
| 工单/处理人查询、统计、台账预览 | `workorder:read` | 没有权限时不进入模型工具列表，调用仍再次拒绝 |
| 知识检索 | `knowledge:read` | 复用现有 Retriever 与 citation 事件 |
| 拟定/创建工单、指派处理人 | `workorder:create`、`workorder:assign` | 需要人工审批；批准前零写入 |

## 4. JSON 与 SSE 契约

### 4.1 通用兼容规则

HTTP 请求继续使用现有 `POST /chat/stream` JSON：`query`、`thread_id`、`route="work_order_ops"`、可选 `model` 与 `extra`。普通 HTTP 失败继续使用：

```json
{"detail":{"code":"...","message":"..."}}
```

SSE 继续使用现有统一信封：`type`、`run_id`、`event_id`、`sequence`、`trace_id`、`timestamp`、`data`。消费者必须按 `sequence` 排序/去重，并忽略未知扩展事件；因此旧客户端仍能显示文本和稳定事件，新客户端可渲染业务结果。

业务事件仅使用 `x.work_order_ops.*`，由 domain 写入 `OUTBOUND_EXTENSIONS_KEY`，最终仍由 Lifecycle 统一持久化并推送。每个 payload 使用 `schema_version: 1`；破坏性变更创建新事件类型或升版本，旧字段保留一个次要版本的兼容期。

### 4.2 列表事件

`x.work_order_ops.list` 用于工单、处理人或台账列表：

```json
{
  "schema_version": 1,
  "resource": "work_orders",
  "title": "待处理高优先级工单",
  "columns": [
    {"key":"id","label":"工单号","data_type":"string"},
    {"key":"title","label":"标题","data_type":"string"},
    {"key":"status","label":"状态","data_type":"string"},
    {"key":"priority","label":"优先级","data_type":"string"},
    {"key":"assignee_name","label":"处理人","data_type":"string"}
  ],
  "rows": [{"id":"WO-1001","title":"网络告警","status":"open","priority":"high","assignee_name":"张三"}],
  "total": 1,
  "truncated": false
}
```

`rows` 只包含当前调用方可见且已脱敏的字段；`truncated=true` 时客户端应提供“结果已截断”的提示，而不是猜测全量数据。

### 4.3 图表事件

`x.work_order_ops.chart` 采用不依赖图表库的通用数据集：

```json
{
  "schema_version": 1,
  "chart_type": "bar",
  "title": "按状态统计工单",
  "x_axis": {"label":"状态","categories":["open","in_progress","closed"]},
  "series": [{"name":"工单数","data":[12,8,25]}],
  "unit": "件"
}
```

首版允许 `bar`、`line`、`pie` 三种 `chart_type`。客户端不支持某一图形时，必须退化为标题、类别和序列值组成的列表；不得因为无法绘图而丢弃业务结果。

### 4.4 台账预览与创建结果

`x.work_order_ops.ledger_preview` 是审批前的只读草稿：

```json
{
  "schema_version": 1,
  "draft_id": "draft-...",
  "work_order": {"title":"网络告警","priority":"high","assignee_id":"A-01"},
  "ledger": {"summary":"待审核创建工单","source":"assistant"},
  "approval_required": true
}
```

`x.bridge.approval_required` 是唯一的审批等待信号。它的 `data` 除现有字段外必须携带平台可持久化的通用 action envelope：

```json
{
  "tool": "create_work_order",
  "timeout_seconds": 1800,
  "action": {
    "type": "work_order_ops.create_v1",
    "payload": {"draft_id":"draft-...","title":"网络告警","priority":"high","assignee_id":"A-01","ledger_summary":"待审核创建工单"}
  }
}
```

Lifecycle 必须在发出审批事件前校验 `action.type` 非空、`payload` 为 JSON 对象，并将 action、请求人 `RunContext` 快照、route、run/thread/tenant、审批序号一起写入 ApprovalStore。模型不得在批准后重新生成或更改该 payload；审批人审核的是已持久化的这份草稿。

批准后，Lifecycle 重获线程锁，以存储的请求人上下文再次调用 Policy 的 `invoke_tool` 决策，并要求当前审批人仍具有 `approval:decide`。只有两项均通过才调用 `ApprovalResumeExecutor`。executor 的 domain handler 在事务成功提交后返回 `x.work_order_ops.work_order_created`：

```json
{
  "schema_version": 1,
  "work_order_id": "WO-1002",
  "ledger_id": "LG-1002",
  "assignee_id": "A-01",
  "status": "open"
}
```

拒绝、超时、策略复检失败、处理人失效或事务失败时，不发 `work_order_created`，也不得有任何工单/台账写入；平台以 `x.bridge.approval_resolved` 和终端事件表达结果。若 executor 失败，Lifecycle 发稳定 `error` 并以 `error` 终端，而不是伪造成功的 `tool_result`。

## 5. 业务流程与失败语义

```text
查询 / 统计 / RAG
  → 调用只读工具 → list/chart/citation 扩展事件 → done

创建工单
  → 校验处理人、查询必要知识 → ledger_preview
  → approval_required + 已持久化 action envelope（释放 thread 锁）
  → approve：重验 Policy / 审批人 → 同 run 调 executor
             → 单一事务写工单 + 台账 → work_order_created → done
  → deny / timeout：零写入 → approval_resolved → done
```

查询不到数据返回空列表或零值图表，不把“没有权限”“后端失败”“没有匹配项”混为同一种结果：权限错误由 Policy 拒绝，依赖故障走 `error`，空查询结果在业务 payload 中表达。RAG 超时或 external 后端失败遵从配置的降级策略，并在文本/业务结果中可识别地说明知识未命中或暂不可用。

创建工单与创建台账必须在同一业务事务中完成；任何一步失败均回滚。审批恢复时重新校验请求人权限、审批人权限、处理人有效性与租户归属。请求人上下文快照和复检结果要写审计，便于解释“请求时允许、批准时被拒绝”的情况。

## 6. 测试与验收

新增 API 级测试覆盖：

- `workorder:read` / `knowledge:read` / 创建与指派权限的列表过滤及执行期二次拒绝；
- 跨租户工单、处理人、台账与知识检索均不可访问；
- `list`、`chart`、`ledger_preview` payload 符合字段约定；
- citation 采用现有 `x.bridge.citation` 契约；
- 审批前、拒绝、超时均零写入；批准后工单与台账同时存在；
- 处理人失效、请求人权限复检失败、重复审批、事务失败和恢复竞争均不产生部分写入；
- ApprovalStore 持久化的 action 与实际写入字段完全一致，批准后不重新生成草稿；
- Fake 事务的回滚语义与 Postgres 事务一致；executor 未登记 action、executor 异常时均发 `error` 且不伪造成功；
- 旧客户端忽略 `x.work_order_ops.*` 仍能接收 `start`、稳定事件及 `done`。

手工验收以新环境、脱敏数据、真实 `langchain_pg` 路径和 external 检索路径各跑一轮为准。P2 再补全生产依赖故障、备份恢复和双实例验证。

## 7. 实施范围

预期新增/修改范围：

- `apps/api/domains/work_order_ops/`：业务状态、图、工具、注册与说明；
- `apps/api/migrations/`：脱敏工单/台账/处理人表与种子；
- `apps/api/tests/`：domain、审批与 SSE 契约测试；
- `packages/core`：通用事务与审批恢复 Port、Lifecycle 接口及 Fake 测试；
- `apps/api/adapters/`：Postgres 事务适配与 app 侧审批 action registry；
- `docs/`：参考案例运行说明、支持矩阵、P0 版本口径与发布说明。

核心改动严格限于不含业务名的通用 Port、Lifecycle 注入点和契约测试；不得为本案例写死 route、表名、事件类型或权限字符串。除上述两项通用能力外，不扩张核心范围。
