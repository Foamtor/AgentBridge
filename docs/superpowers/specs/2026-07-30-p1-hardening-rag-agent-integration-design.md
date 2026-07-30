# P1 审批加固与 RAG-Agent 只读集成设计

> **状态：** 已获用户设计确认，待书面复核  
> **日期：** 2026-07-30  
> **关联：** [工单黄金案例设计](./2026-07-30-work-order-ops-golden-case-design.md) · [P1 实施计划](../plans/2026-07-30-p1-work-order-ops.md)

## 1. 目标

修复 P1 审阅发现的审批恢复、事件顺序、Run 投影、工具双检和动态草稿问题，并让 `work_order_ops` 在不修改 RAG-Agent 项目及其数据的前提下，只读复用其 PostgreSQL/pgvector 知识库和 embedding 服务。

完成后必须证明：

1. 用户自然语言或传统业务系统的结构化输入可生成同一类型化工单草稿；
2. 草稿、审批 action 和最终业务写入字段完全一致；
3. 查询、RAG 和草稿工具均经过工具列表过滤与调用期 Policy 再鉴权；
4. 审批失败、重试、租约接管和结果投递不会产生重复事件序号、错误终态或重复业务数据；
5. RAG-Agent 知识只映射给固定演示租户，且 AgentBridge 不写入 RAG-Agent 数据库。

## 2. 明确边界

### 2.1 RAG-Agent 不受修改

- 不修改 `D:\WorkSpace\code\project\RAG_Agent` 的源码、配置或数据库 schema。
- 不向 RAG-Agent 的 `kb_document`、`kb_section`、`kb_chunk` 或其它表执行 DDL/DML。
- 不复制 RAG-Agent Python 包到 AgentBridge，也不从 AgentBridge import 其模块。
- 不重新生成或更新已有 embedding。
- 允许的外部操作只有只读 PostgreSQL 查询、schema/能力探测和 embedding HTTP 查询。

### 2.2 固定演示租户

- 固定租户标识为 `rag-agent-demo`。
- `RagAgentPgRetriever.similarity_search(..., tenant_id=...)` 只有在 `tenant_id == "rag-agent-demo"` 时访问外部数据库。
- 其它租户返回空命中，且不得建立数据库连接或调用 embedding 服务。
- 该映射代表共享知识被显式授权给一个演示租户，不声称 RAG-Agent 原始数据具备租户标签。
- `007_work_order_demo_tenant.sql` 新增 `rag-agent-demo` 的脱敏工单、处理人和台账种子，保证同一演示身份能完成结构化查询、RAG 和审批写入闭环；原有其它租户种子只保留作隔离测试。

### 2.3 现有后端兼容

保留 `fake`、`langchain_pg` 和 `external` 的现有行为。新增独立配置：

| 变量 | 值或约束 |
|---|---|
| `KNOWLEDGE_BACKEND` | `rag_agent_pg` |
| `RAG_AGENT_PG_DSN` | 必填；由部署环境提供的只读 PostgreSQL DSN |
| `RAG_AGENT_DEMO_TENANT` | `rag-agent-demo` |
| `RAG_AGENT_EMBED_API_BASE` | `http://127.0.0.1:8080/v1` |
| `RAG_AGENT_EMBED_API_KEY` | 本地服务使用 `EMPTY` |
| `RAG_AGENT_EMBED_MODEL` | `BAAI/bge-m3` |
| `RAG_AGENT_EMBED_DIMENSIONS` | `512` |

生产和真实验收必须使用仅有 `CONNECT`、目标 schema `USAGE` 和 `SELECT` 权限的数据库账号。代码仍以 `READ ONLY` 事务作为第二层保护。

## 3. 总体架构

```text
POST /chat/stream
  → work_order_ops graph
     → 受 ToolGuard 保护的 ToolNode / 工具调用入口
        ├─ list_work_orders → TransactionalDataSource
        ├─ work_order_statistics → TransactionalDataSource
        ├─ search_work_order_knowledge → Retriever
        └─ prepare_work_order_draft → CreateWorkOrderDraft
  → x.work_order_ops.list / chart / ledger_preview / x.bridge.citation
  → x.bridge.approval_required（持久化不可变 action）
  → POST /approvals/{approval_id}
  → 审批人权限 + 请求人 Policy 复检
  → 带 execution_token 的原子 claim
  → 单事务创建 work_order + ledger
  → 持久化 result
  → 唯一递增 sequence 的 created + done
  → RunStore / MessageStore 终端投影
```

`RagAgentPgRetriever` 是 adapter，只在 `apps/api/lifespan.py` 及其工厂中创建。domain 只依赖注入的 `Retriever` Port。

为支持自然语言生成类型化工具调用，通用 `LLMGateway.chat` 增加可选的 `tools` 和 `tool_choice` 参数。Direct/Alias gateway 只负责将已由 Lifecycle 过滤和包装的工具绑定到宿主模型；core 不认识工单字段或业务工具名。现有不传工具的调用保持兼容。

若宿主模型不支持 `bind_tools`，带工具的调用以稳定的 `llm_tool_binding_unsupported` 失败；不得绕开 guarded tools 直接调用原始工具。

## 4. 动态工单草稿

### 4.1 双入口

自然语言是主要入口。graph 使用 `RunContext.metadata["llm_gateway"]`，按请求的模型别名调用：

```python
await gateway.chat(
    messages,
    ctx=ctx,
    model=model_alias,
    tools=[guarded_prepare_tool],
    tool_choice="prepare_work_order_draft",
)
```

LLM 返回的 tool call 再交给使用同一组 guarded tools 的 `ToolNode` 执行。工具参数为：

```json
{
  "title": "园区网络告警",
  "priority": "high",
  "assignee_id": "assignee-demo-a",
  "ledger_summary": "用户报告园区网络中断，需立即排查"
}
```

传统业务系统可以在请求中提供：

```json
{
  "extra": {
    "work_order_draft": {
      "title": "园区网络告警",
      "priority": "high",
      "assignee_id": "assignee-demo-a",
      "ledger_summary": "用户报告园区网络中断，需立即排查"
    }
  }
}
```

结构化输入跳过 LLM 参数提取，但不能跳过类型校验、工具调用期 Policy、处理人检查或人工审批。

`work_order_ops` input builder 将 `query`、`model` 和 `extra.work_order_draft` 写入 graph state。graph 只用关键词判断是否进入创建分支，不用关键词推断或填充草稿字段。

### 4.2 单一草稿来源

- 两个入口最终都调用 `prepare_work_order_draft`。
- `CreateWorkOrderDraft` 是唯一字段和长度校验模型。
- 工具输出的 `model_dump()` 同时用于 `ledger_preview` 和 `approval_required.action.payload`。
- 批准后只能执行 ApprovalStore 中持久化的 payload，禁止重新调用模型或重新生成字段。
- 草稿形成前查询当前租户可用处理人；批准执行时在业务事务内再次检查处理人所属租户和 active 状态。
- 自然语言缺少标题、优先级或处理人时返回可识别的补充信息提示，不得用固定默认值静默补齐并进入审批。

## 5. 工具权限与图执行

- graph 不直接调用 `ctx.metadata["data_source"]` 或 `ctx.metadata["retriever"]`。
- graph 不手写 `workorder:*`、`knowledge:read` 权限判断。
- Lifecycle 先用 `Policy.filter_tools` 过滤模型或 graph 可见工具。
- ToolNode 或统一工具调用入口使用 `guard_tools` 包装后的工具，调用时再次执行 `Policy.decide(action="invoke_tool")` 并记录审计。
- graph builder 只接收 Lifecycle 传入的 guarded tools，并按工具 `name` 选择可调用项；不得回退到模块级原始工具。
- 缺少 `workorder:read` 时不产生工单列表或统计业务结果；缺少 `knowledge:read` 时不执行知识检索；缺少 create/assign 任一权限时不能生成审批 action。
- 权限拒绝、知识空命中和知识依赖故障是三个不同结果。

## 6. RAG-Agent 只读 Retriever

### 6.1 启动探测

`KNOWLEDGE_BACKEND=rag_agent_pg` 时，adapter 工厂必须验证：

1. DSN、embedding base URL、模型名和维度均非空；
2. PostgreSQL 可连接；
3. `vector` 扩展存在；
4. `kb_document`、`kb_section`、`kb_chunk` 存在；
5. `kb_chunk.embedding` 的实际类型为 `vector(512)`；
6. embedding HTTP 响应向量维度为 512。

探测只使用只读查询。任一条件不满足时启动失败，并指出缺失能力，不执行自动迁移。

### 6.2 检索

检索在 `SET TRANSACTION READ ONLY` 的事务内完成：

1. 调 embedding HTTP 服务得到查询向量；
2. 从 active `kb_document` 关联 `kb_section`、`kb_chunk`；
3. 使用 cosine distance 取得 top-k；
4. 将 RAG-Agent 字段规范化为 AgentBridge `KnowledgeHit`：

```text
chunk_id  ← kb_chunk.chunk_id
doc_id    ← kb_document.doc_id
text      ← kb_chunk.content
tenant_id ← rag-agent-demo
score     ← 1 - cosine_distance
metadata  ← 标题、section_id、heading 和只读来源标识
```

查询不得返回 embedding 原值、数据库内部自增主键或敏感连接信息。

### 6.3 失败语义

- 非演示租户：`[]`，且不访问外部依赖。
- 合法演示租户无匹配：`[]`，citation 为空。
- 数据库、pgvector、schema 或 embedding 不可用：抛出稳定的知识后端异常，由 Lifecycle 输出 `knowledge_backend_unavailable`。
- 对外错误消息脱敏；原始异常只写受控日志和审计。

## 7. 审批状态机加固

### 7.1 Execution fencing

ApprovalStore 的 claim 结果增加 `execution_token`，每次从 `approved_pending_execution` 或 `retryable_failed` 进入 `executing` 时生成新 token。

以下操作必须同时匹配 `(approval_id, tenant_id, status="executing", execution_token)`：

- `mark_succeeded`
- `mark_retryable_failed`
- 任何延长租约的操作

`recover_expired_execution` 仅在租约过期时原子清除旧 token 并进入 `retryable_failed`。旧 worker 使用旧 token 完成时得到 `None`，不得发结果事件或覆盖新 worker。

Lifecycle 只有在 `mark_succeeded(..., execution_token=...)` 返回当前成功记录后才能发业务结果；返回 `None` 表示 claim 已失效，当前 worker 静默结束并读取最新状态。

### 7.2 Sequence cursor

ApprovalStore 持久化 `last_sequence`，并提供原子 `next_sequence(approval_id, tenant_id) -> int`。创建审批时保存 approval event 的 sequence；恢复过程每次发事件前领取下一序号。失败后重试成功必须继续递增，不得复用此前 `error` 或 `done` 的 sequence。

EventLog 仍保持 append-before-SSE。领取序号成功但 EventLog append 失败时允许出现序号缺口，但禁止重复序号。

### 7.3 终端投影

action 与 legacy 审批共享一个终端收尾函数。下列路径都必须更新 RunStore 和 MessageStore：

- deny / timeout → `done`
- 请求人或审批人权限复检失败 → `done`，业务 skipped
- executor 异常 → `error`
- executor 成功 → `done`
- 业务成功但结果事件投递失败 → Run 状态仍为 `done`，同时增加 `result_delivery_error`，不得重新执行业务动作

### 7.4 决策转换

- `pending + approve` → `approved_pending_execution`
- `pending + deny/timeout` → `denied`
- `approved_pending_execution/retryable_failed + deny` → 原子 `denied`
- `executing + deny` → 返回冲突，不伪造拒绝事件
- `succeeded/denied + 任意重复决策` → 返回已存在终态，不再次执行或发重复业务结果

### 7.5 Pending 超时恢复

审批记录持久化 `approval_expires_at`。ApprovalStore 增加：

```python
async def list_expired_pending(
    self, *, now: datetime, limit: int = 100
) -> list[dict[str, Any]]: ...
```

内存后台任务只负责低延迟体验；Lifecycle 提供 `expire_pending_approvals(now, limit)`，逐条调用已有原子 `decide(..., decision="timeout")` 并完成终端事件与 Run 投影。`lifespan.py` 启动一个可取消的周期任务，并在启动后立即执行一次。重启不能让 pending 审批永久悬挂。

## 8. API 与错误安全

- `/approvals/{id}` 使用显式响应 DTO，不直接返回数据库内部记录。响应只包含 `approval_id`、`status`、`decision`、`reason`、`run_id`、`thread_id` 和已经标准化的业务 `result`；不包含 action、请求人快照、execution token、租约、内部错误或 DSN。
- executor、SQL、schema 和网络异常不原样进入 SSE 或 HTTP 响应。
- 稳定错误至少包括：
  - `approval_execution_failed`
  - `approval_state_conflict`
  - `knowledge_backend_unavailable`
  - `approval_result_delivery_failed`
- 详细异常进入日志、审批记录的受限内部字段和审计；不得包含 token、DSN 或文档正文。

## 9. 测试与验收

### 9.1 自动化

新增测试覆盖：

- 失败后重试成功的 sequence 唯一且严格递增；
- 过期 execution token 不能完成新 claim；
- approve、deny、timeout、权限拒绝、executor 异常和投递失败后的 Run/Message 投影；
- approved/retryable 状态的 deny 和 executing 状态冲突；
- pending 审批跨重启超时；
- 并发 approve 只执行一次；
- 请求人权限撤销、审批人无权限、缺 create/assign 任一权限、跨租户审批均零写入；
- 动态自然语言草稿与 `extra.work_order_draft` 的预览、action、最终写入完全一致；
- 工单与台账第二次写入失败时整体回滚；
- graph 实际调用受 ToolGuard 保护的工具并产生拒绝审计；
- 旧客户端忽略 `x.work_order_ops.*` 后仍正确处理稳定事件；
- RAG-Agent 非演示租户不连接外部依赖；
- schema/维度错误、embedding 失败、数据库失败和真实空命中语义；
- PostgreSQL `claim → 业务提交 → 未 mark → 新实例接管` 只生成一份业务数据。

### 9.2 真实环境

使用现有 RAG-Agent 环境执行只读验收：

- PostgreSQL/pgvector：当前探测为 pgvector `0.8.2`、`kb_chunk.embedding vector(512)`；
- 数据规模：当前为 424 个文档、5,942 个已有向量块；
- embedding 服务：当前 `http://127.0.0.1:8080/health` 可用；
- RAG-Agent API 当前不作为依赖，后台未启动不影响直接只读检索。

验收只记录查询、命中数量、citation 标识、租户隔离结果和耗时，不复制文档正文或凭据。

### 9.3 完成门禁

```powershell
$env:KNOWLEDGE_BACKEND='fake'
python -m pytest packages/core/tests apps/api/tests -q
python -m ruff check packages/core/src apps/api
python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
python scripts/import_scan_core.py
python scripts/import_scan_rag_engines.py
git diff --check
```

真实 PostgreSQL/RAG-Agent 测试不得由 Fake 测试替代。公开发布仍受 P2/P3、安全报告渠道和发布工程门槛约束。

## 10. 数据库迁移

不回写已经存在的 `004`/`005` migration：

- `006_approval_hardening.sql`：为 `approval_records` 增加 `execution_token`、`last_sequence`、`approval_expires_at` 及过期 pending 扫描索引。
- `007_work_order_demo_tenant.sql`：幂等新增 `rag-agent-demo` 的脱敏处理人、工单和台账种子；保留其它租户种子用于隔离测试。

RAG-Agent 数据库不执行 AgentBridge migration。

## 11. 非目标

- 不修改或重构 RAG-Agent。
- 不为 RAG-Agent 增加新的 HTTP API。
- 不同步、复制或重新摄取其知识数据。
- 不将固定演示租户方案描述为通用多租户知识治理。
- 不在本轮实现 outbox、跨数据库分布式事务或多机生产承诺。
