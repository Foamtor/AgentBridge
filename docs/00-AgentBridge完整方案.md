# AgentBridge 完整方案

> **当前首发定位**：面向 Vibe Coding 的自托管业务 AI 开发底座；不是云托管 Studio，也不是开箱即用的客户业务系统。
>
> **标准旅程**：clone / fork → AI 阅读 `AGENTS.md` 与 AI 手册 → 参考 `work_order_ops` → 按规则编写 domain / tools / tests → 用 Docker Compose 验证。
>
> **一句话**：平台统一处理 JSON/SSE、权限、审批、审计、生命周期和 RAG Port；业务开发者与 AI 只实现自己的流程、工具和结构化结果。
>
> **当前发布范围**：以 [v0.1.0 首次开源发布 Spec](./superpowers/specs/2026-08-01-p3a-open-source-release-readiness-design.md) 与对应 Plan 为准。下面的能力架构仍是长期约定；SDK、多 Agent、多机与生产部署是进阶能力，不是首发新人路径。

---

## 一、愿景与边界

### 1.1 为什么做

业务系统要加对话、工具、RAG、审批、多 Agent，不想从零拼：SSE、线程锁、取消、鉴权、权限、落库、可观测、模型路由。

AgentBridge 提供**统一的公共能力**；业务作者只注册流程、工具，以及（可选）检索/策略声明。

### 1.2 做 / 不做

| 做 | 不做 |
|----|------|
| 自托管；多个业务插件注册表；稳定 SSE + 扩展事件 | 替代 LangGraph Platform 云托管 / 官方 Studio |
| 以已经写入成功的事件为准；消息/审计为投影 | 无契约的「随便推 JSON」 |
| Policy 按 action 统一 tool/数据/输出/审批 | 假装通用 IAM 产品 |
| 多租户硬隔离（键空间级） | 仅靠业务 SQL「记得写 tenant_id」 |
| LLM Gateway Port（路由/降级/PII/成本） | 绑定单一模型厂商 |
| 单机默认；多机有明确矩阵 | 宣称「默认安装后立刻多副本无脑扩」却仍用进程内锁 |
| 多 Agent（supervisor/subgraph） | AutoGen 式任意 GroupChat 研究框架 |
| SDK（TS/Python）+ 管理 API + CLI 回放 | 完整商业控制台 SaaS |

### 1.3 成功标准（能力完备度，非人天）

| 维度 | 标准 |
|------|------|
| 安全 | 角色×tool 权限矩阵测试 0 漏网；跨租户读 memory/RAG/消息被 Port 拒绝 |
| 可运维 | 任意 `run_id` 可回放**已提交**事件流；OTel span 与 SSE `run_id` 可关联 |
| 可接入 | L1 跑通；L2 带权限查库；L3 = 已有审计 + 单机运维能力；进阶官方示例可以演示 |
| 可演进 | Pipeline/Port 插件；未装则 noop；Gateway 有过渡期 |
| 诚实 | README 写明单机/多机矩阵、包名与产品名差异、弱项 |

---

## 二、用户旅程

### 2.1 首发路径（优先）

```text
读仓规则 → 写/改 domain 与 tools → Compose 启动 → 在 AI 控制台验证业务事件
```

`work_order_ops` 用脱敏数据演示查询、图表、citation、台账草稿与人工审批。它是给人和 AI 的参考实现，不是客户业务前端。

### 2.2 进阶能力地图

| 级别 | 用户做到什么 | 主要里程碑 |
|------|----------------|------------|
| **L1** | 起服务 → 用模板建业务插件 → SSE 对话 | M0–M1 |
| **L2** | JWT 角色 → tool 可见性正确 → 消息可查 →（可选）查库 | M2–M3 |
| **L3** | **已有审计（M2）** + 限流/metrics/OTel + 单实例部署清单 | M2 + M4 |
| **进阶 A** | 写入类 tool 审批；超时/转交可测 | M6 |
| **进阶 B** | 摄取 + RAG citation + 租户隔离检索 | M7 |
| **进阶 C** | 多 Agent；单流带 `agent_id`；子 run 可追溯 | M8 |
| **进阶 D** | SDK；管理 API；`replay` CLI | M8（replay 自 M2b） |

---

## 三、目标架构

### 3.1 总图（控制流）

Policy / Gateway **不是**与 Lifecycle 并列的 Pipeline 步骤，而是执行期依赖：

```text
Management API / TS SDK / Python SDK / CLI
                    │
JWT/OIDC → Middleware(auth, quota, request-id)
                    │
            RequestPipeline（before 插件）
                    │
                    ▼
              RunLifecycle
           lock → stream → release
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   LLM Gateway   图/ToolNode   emit 路径
   (模型出口)    Policy.decide  │
        │        Tool Runtime   │
        │           │           ▼
        │           │     ① EventLog.append（先）
        │           │     ② sink.emit（后）
        └───────────┴───────────┘
                          │
              Message / Audit 投影（终端后或异步）
              Metrics/OTel：执行期实时打点（非必须从 EventLog 派生）
```

### 3.2 当前 → 目标

**当前（M0）**

```text
HTTP → RunLifecycle → LangGraphRuntime → EventSink(SSE)
```

**目标**

- Middleware：鉴权、配额/限流、请求 ID
- Pipeline：有序 `before_run` / `after_terminal` 插件（校验、tool 列表策略、上下文组装、审计摘要等）
- RunLifecycle：lock → stream → emit → release；持有对 Gateway、Policy、EventLog 的依赖（经构造注入）
- 向后兼容：`app.state.run_lifecycle` 与 `app.state.pipeline` 并存

### 3.3 RequestPipeline 插件模型

```python
class PipelinePlugin(Protocol):
    name: str
    order: int
    async def before_run(self, req: PipelineRequest) -> PipelineRequest: ...
    async def after_terminal(self, req: PipelineRequest, result: RunResult) -> None: ...
```

官方示例：`InputValidatorPlugin`、`ToolPolicyPlugin`（调用 `PolicyEngine.filter_tools`）、`ContextBuilderPlugin`、`AuditPlugin`。  
组合行为必须有测试（0 / 1 / 多插件）。

---

## 四、冻结契约

> 变更须改版本说明 + 契约测试。

### 4.1 RunContext（两阶段）

```python
class RunContext(BaseModel):
    user_id: str = ""
    tenant_id: str = ""
    roles: list[str] = []
    permissions: list[str] = []
    max_tokens: int | None = None
    max_tool_calls: int | None = None
    deadline_ms: int | None = None
    run_id: str = ""
    trace_id: str = ""
    parent_run_id: str = ""
    agent_id: str = ""
    policy_bundle_version: str = ""
    metadata: dict[str, Any] = {}
```

**阶段 A — 身份上下文（JWT / 开发默认）**  
middleware 填：`user_id` / `tenant_id` / `roles` / `permissions` / 预算类（若来自配置）/ `policy_bundle_version`。  
此时 `run_id` 为空。

**阶段 B — 运行上下文（Lifecycle 创建 run 之后、首个 SSE `start` 之前）**  
写入：`run_id` / `trace_id`（默认可等于 `run_id`）/ 多 Agent 时的 `parent_run_id`·`agent_id`。  
再放入 `configurable[RUN_CONTEXT_KEY]`，供 tool / Gateway / Retriever 使用。

**JWT claims**

| claim | 字段 |
|-------|------|
| `sub` | `user_id` |
| `tenant_id` / `tid` | `tenant_id` |
| `roles` | `roles` |
| `permissions` / `perms` | `permissions` |

**开发态**（`auth_required=false`）：  
`user_id="dev"`, `tenant_id="dev"`, `roles=["admin"]`, `permissions=["*"]`。

**Tool 内唯一合法取值**：`get_run_context(config)`。  
禁止 `ctx: RunContext = None`；禁止 sync 中 `await`。

**Checkpointer 租户键（冻结）**：对外 `thread_id` 不变；写入 LangGraph / Redis 锁的存储键为  
`checkpoint_thread_key(tenant_id, thread_id) == f"{tenant_id}::{thread_id}"`（`tenant_id` 空时用 `"default"`）。  
多机 `ThreadLock.try_acquire` 的首参传 **storage_key**（勿对已前缀键再前缀）。

### 4.2 EventLog：已提交事件才是权威说明

**定义**：EventLog 只包含 **append 已成功提交** 的出站事件。客户端曾见但未提交的帧，不算权威说明。

**Emit 顺序（写死）**：

1. `EventLog.append(run_id, event)` 成功  
2. 再 `sink.emit(event)`  
3. append 失败 → 发（或仅 HTTP/日志）`error`，**终止**该 run；不得在未提交时继续推「已发生」的业务事件  

可选优化：同库 outbox 表 + 异步推送，但仍须「先持久化成功」。

**与断连的关系**：

- 断连 / 取消 = **run 未正常终端或提前终端**，不是「权威说明不可信」  
- 已提交前缀可回放；未提交的尾部不存在于 EventLog  
- Message 投影：在终端事件已提交后，按 run 投影一轮摘要；支持对已提交事件做补偿投影  

**保留策略（默认，与 Plan1 对齐）：**

- **EventLog**：保留**全量已提交**信封（含每条 `text_delta`）；生产库可另配压缩/TTL，但回放语义不变  
- **MessageStore 投影**：终端后将同一 run 的 `text_delta` **合并**为一条 assistant 消息  
- 热数据默认保留 ≥ 30 天；冷归档 / TTL 可配  
- 在线查询以投影表为主；EventLog 服务回放与审计取证  

`agentbridge replay <run_id>`（产品名；包名未改前 CLI 用 `scripts/replay_run.py`）只读已提交事件。

### 4.3 Policy：按 action 决策

```text
allow | deny | require_approval | mask
```

| action | 含义 | 允许的决策 |
|--------|------|------------|
| `list_tools` | 构造 LLM tool list | `allow` / `deny`（deny = 不出现在列表） |
| `invoke_tool` | 执行 tool | `allow` / `deny` / `require_approval` |
| `read_data` | 行/文档读取 | `allow` / `deny` / `mask` |
| `emit_text` | 出站文本（含 delta/最终） | `allow` / `mask` |

```python
class PolicyEngine(Protocol):
    def filter_tools(self, route: str, tools: list, ctx: RunContext) -> list: ...
    def decide(
        self, *, ctx: RunContext, action: str, resource: dict
    ) -> PolicyDecision: ...
```

- `list_tools` 过滤后，`invoke_tool` **仍须**再 `decide` 一次（**M2a / Plan1 必交付**，不可只做列表过滤）  
- `require_approval`：见 §4.6，未批准不执行副作用（**M6 / Plan4**）  
- `mask`：走脱敏管线（用户侧不可逆 / LLM 侧可逆，见产品线 C；**M6 / Plan4**）  
- 每次决策写审计：subject、action、resource、decision、reason_code、policy_version  

匹配：`roles`/`permissions` 与要求有交集即候选；`"*"` 仅开发或显式超级权限。  
**默认姿态**：`read_data` 无规则 → **无数据**；危险写操作无声明 → 可配置默认 `require_approval`。

**M2a 范围**：Plan1 的 `RolePolicyEngine` 对 `list_tools`/`invoke_tool` 实现 `allow|deny`；尚未实现的 action（含 `require_approval`/`mask`/`read_data`/`emit_text`）在 Plan4 前 `decide` 返回 **`deny`**（安全默认）。

### 4.4 SSE 契约

- **稳定九类**：`start` · `step_update` · `text_delta` · `tool_call` · `tool_result` · `done` · `error` · `cancel_requested` · `cancelled`
- **扩展**：`x.<domain>.*`
- **治理扩展（先 `x.bridge.*`）**：
  - `x.bridge.approval_required` / `x.bridge.approval_resolved`
  - `x.bridge.citation`
  - 多 Agent：相关事件 `data.agent_id` / `data.parent_run_id`

信封样例权威说明：`docs/contracts.md`。

### 4.5 多租户硬边界

Port 读写的 `tenant_id` **只来自 RunContext**，调用方不可覆盖为其他租户。  
覆盖范围：EventLog、Message 投影、Audit、Checkpointer 键、Memory、Vector、Prompt 命名空间。  
跨租户：Port 层失败 + 审计 `reason_code=cross_tenant`。

### 4.6 人机审批（HIL）与线程锁

**写死默认语义（M6 官方示例必须遵守）**：

| 项 | 约定 |
|----|------|
| 触发 | `invoke_tool` → `require_approval` 或图内 `interrupt` |
| 锁 | **释放** `thread_id` 锁，run 状态记为 `awaiting_approval`（RunStore）；避免审批挂起占死会话 |
| 事件 | 已提交 `x.bridge.approval_required`（含 `run_id`、tool、超时点） |
| Resume | **同一 `run_id`** 经 `POST /approvals/{id}`（或等价）恢复；恢复时重新 `try_acquire` 锁，失败则 409 |
| 超时 | 默认 **deny**（不执行副作用）+ 已提交 `x.bridge.approval_resolved` + 终端 `done` 或 `error`（实现选一种并固定；推荐 `done` + data 标明未执行） |
| 新 run | 审批等待期间允许同 thread **新 run**（因锁已释放）；若业务要互斥，用 RunStore 策略「有 awaiting 则拒绝」——默认 **允许**，官方示例插件演示默认行为 |

### 4.7 管理面鉴权

| API | 要求 |
|-----|------|
| `/chat/*`、`/threads/*`、`/runs/*`（读本人或本租户） | 业务 Bearer；强制 `tenant_id` 隔离 |
| `/approvals/*` | 业务 Bearer + permission 如 `approval:decide`（可配置） |
| `/admin/*`、`/prompts/*`（写） | 业务 Bearer + `admin:*` 或独立 admin audience（二选一，部署文档写死） |
| `/ingest`（写） | 业务 Bearer + **`knowledge:write`**（现行代码）；若部署要收紧为 `admin:*`，改实现并同步 contracts |
| `/metrics`、`/ready`、`/health` | `/health` 常公开；`/ready`/`/metrics` 建议内网或独立鉴权 |

禁止「有任意合法 JWT 即可改策略包」。

### 4.8 多 Agent 的 SSE 形态

- **默认**：**单 HTTP SSE 流**，事件 `data` 带 `agent_id`（及可选 `parent_run_id`）  
- 子图仍属同一 `run_id`，除非显式创建子 run（若创建，则 `parent_run_id` 指向父，**另开 stream 非默认**）  
- TS SDK 按 `agent_id` 分组展示，不默认多连接

### 4.9 出口治理职责边界

| 组件 | 管什么 |
|------|--------|
| Policy `emit_text` / `read_data` + DataMasker | 该不该出、出前 mask（含可逆 token） |
| LLM Gateway | 模型 IO 的 PII、路由、降级、成本；可逆还原按权限在出站给用户前 |
| SafetyHooks | emit 前正则/规则兜底告警或打码（最后一道） |
| OutputGovernor | 可选：幻觉自检、结构化校验等 **增强**；默认 noop，不替代上三者 |

---

## 五、内核三件套

### 5.1 PolicyEngine

见 §4.3。声明：tool 元数据 / `@secure_tool`、数据规则包、输出 PII 类别。

### 5.2 LLM Gateway（含过渡期）

```python
class LLMGateway(Protocol):
    async def chat(self, messages, *, ctx: RunContext, model: str | None) -> ...: ...
    async def stream(self, messages, *, ctx: RunContext, model: str | None) -> AsyncIterator: ...
```

职责：路由与降级、超时重试、配额与成本、PII、PromptRegistry 集成。

**迁移（写死）**：

| 阶段 | 行为 |
|------|------|
| M5 前 | 图/Runtime 可直连厂商客户端（现状） |
| M5 | 引入 Gateway；`LLM_BACKEND=direct\|gateway`（默认 `direct` 直至官方示例切换） |
| `direct` | Gateway adapter 透传现有构造方式，业务插件代码可暂不改 |
| `gateway` | Runtime **只**经 Gateway；域禁止直接 `ChatOpenAI(...)` 进主路径（lint/评审） |
| MUST | 「模型经 Gateway」在 **默认 `gateway` 且文档切换后** 生效，而非 M0 起 |

### 5.3 EventLog

```python
class EventLog(Protocol):
    async def append(self, run_id: str, event: dict) -> None: ...
    async def list(self, run_id: str) -> list[dict]: ...
```

实现：Postgres append-only（单机默认）；多机共用集中存储。  
语义见 §4.2。

---

## 六、四条产品线

### 6.1 产品线 A — 对话与编排

| 能力 | 说明 |
|------|------|
| 多个业务插件注册表 | graphs / tools / input_builders；域健康与元数据 |
| 域热配置 | ConfigProvider |
| 取消 | 协作式（已有）；副作用文档化；可选硬取消 |
| RunStore | 状态含 `awaiting_approval`；`GET /runs` |
| 入站扩展 | 文件/图像经 `extra`；可选扫描钩子 |

**官方示例插件**：`echo`、`demo_tools` + `demo_readonly`（M3）。  
默认安装保持瘦；进阶官方示例可 extra/示例目录，避免模板巨仓（实现时选定）。

### 6.2 产品线 B — 知识与记忆

| 能力 | Port | 默认 |
|------|------|------|
| 窗口裁剪 | ContextManager | tiktoken 预算 |
| 长期记忆 | MemoryStore | noop；mem0 等 **extra** |
| 检索 | Retriever | pgvector；LlamaIndex **extra** |
| 摄取 | Ingest | CLI + API；tenant namespace |
| 引用 | SSE | `x.bridge.citation` |

缓存键必须含 `tenant_id`；召回超时失败默认不阻塞主路径。

### 6.3 产品线 C — 安全与治理

| 层 | 能力 |
|----|------|
| Tool | list + invoke 策略；超时/重试；可选幂等键（请求 `extra.idempotency_key` 或头 `Idempotency-Key`，M6 钉死一种） |
| 数据 | DataSource（Postgres 一等）；DataFilter 白名单 + 参数化 + deny-by-default |
| 脱敏 | 用户侧 `@mask_fields`；LLM 侧可逆 DataMasker（`token_map` 绑 run；跨 turn 复用默认关） |
| 出口 | 见 §4.9 |
| 人机 | 见 §4.6 |
| 审计 | append-only；导出（M10 加强） |
| 输入 | InputValidator |

### 6.4 产品线 D — 协作与扩展

| 能力 | 说明 |
|------|------|
| 多 Agent | 见 §4.8；共享 Policy 与 Gateway |
| TS / Python SDK | stream、重连、九类、审批状态机；业务作者辅助 |
| 管理 API | 见 §4.7 |
| PromptRegistry | 版本、变量、回滚 |
| Eval | 官方示例对话；越权回归；CI 可选 |
| CLI | `replay`、`ingest`、`scaffold`（入口名随品牌重命名） |

**官方示例插件**：`demo_approval_write`、`demo_rag`、`demo_multi_agent`。

---

## 七、HTTP / API 面

| 方法 | 路径 | 说明 | 里程碑 |
|------|------|------|--------|
| GET | `/health` | 存活 | M0 |
| GET | `/ready` | 依赖就绪 | M4 |
| POST | `/chat/stream` | SSE | M0 |
| POST | `/chat/cancel` | 取消 | M0 |
| GET | `/threads`、`/threads/{id}/messages` | 列表/投影 | M2b |
| GET | `/runs`、`/runs/{id}` | RunStore | M2b |
| GET | `/runs/{id}/events` | EventLog | M2b |
| GET | `/metrics` | Prometheus | M4 |
| GET/POST | `/approvals/*` | 审批 | M6 |
| POST | `/ingest` | 摄取 | M7 |
| `/admin/*`、`/prompts/*` | 管理/提示词 | M5–M8 |

认证与鉴权分层见 §4.7。

---

## 八、依赖与 extras

### 8.1 Core

必装保持瘦：`langgraph`、`langchain-core`、`pydantic`。  
按需：tiktoken、tenacity 等。

### 8.2 Extras

| extra | 内容 |
|-------|------|
| `postgres` | checkpointer / EventLog / Message / DataSource |
| `memory` | mem0 等 |
| `rag` | pgvector；optional LlamaIndex（pin） |
| `mask` | 可逆脱敏高级实现 |
| `otel` | OpenTelemetry |
| `redis` | 分布式锁 / 限流 |

### 8.3 不用或替换

slowapi → 自研/Redis；Langfuse 不强制自托管；Guardrails 不必装。

---

## 九、部署矩阵

| 模式 | 锁 | 限流 | EventLog | 说明 |
|------|----|------|---------|------|
| 本地 | 进程内 | 可选 | 内存或 PG | 开发 |
| 单机生产 | 进程内 | 进程内或 Redis | Postgres | **v1.0 主承诺** |
| 多机 | Redis/DB | Redis | 集中 PG | **M9** |

---

## 十、AI 友好与官方资产

### 10.1 核心规则（MUST）

1. `application` 禁止 import `adapters`  
2. 业务插件代码不持有 `EventSink`  
3. `core` 的 `src/` 不能出现业务插件名称  
4. adapter 只在服务启动时的组装代码构造  
5. `list_tools` 为 deny 的 tool 不得进 LLM tool list  
6. 跨租户在 Port 层失败  
7. 默认 `LLM_BACKEND=gateway` 后，模型调用必须经 Gateway  

### 10.2 模式库与脚手架

`_patterns/`：readonly_query、write_with_approval、rag_qa、multi_agent_delegate  
`scaffold` 生成域 + 权限矩阵测试骨架；契约 fixture 前后端共享。

### 10.3 测试策略

单元（Port fake）· 权限矩阵 · SSE 契约 · 集成 FakeRuntime/FakeGateway · 回放一致性 · 跨租户拒绝 · import-linter  
**HIL**：锁释放、超时 deny、resume 同 `run_id` 重获锁  
**EventLog**：append 失败不得已发射业务事件

---

## 十一、能力里程碑（按能力划分、不按工期估人天）

| 里程碑 | 主题 | 现场怎么验收 |
|--------|------|----------|
| **M0** | 编排本平台 | echo / demo_tools；409；cancel |
| **M1** | 包装与 AI 友好 | scaffold；指令 CI；L1 文档 |
| **M2a** | 身份 + Tool Policy（**list + invoke 双检**）+ 审计 + Pipeline 骨架 | 两角色 tool 矩阵；invoke deny 可测；审计有记录 |
| **M2b** | EventLog（append-before-emit，全量已提交事件）+ 消息/Run 投影（delta 合并）+ replay | messages 可查；replay 与已提交事件一致；append 失败不推业务事件 |
| **M3** | DataSource + demo_readonly | 权限下查库 |
| **M4** | 单机运维能力 | `/ready` `/metrics` 限流 OTel；**InputValidator**；deploy 清单 |
| **M5** | Gateway（含 direct 过渡）+ ContextManager + Prompt | `gateway` 模式换模型不改域；裁剪可测 |
| **M6** | DataFilter、双轨脱敏、Approval（§4.6） | 审批官方示例；脱敏用例；无规则无数据 |
| **M7** | Memory extra、RAG、citation | 租户隔离检索 |
| **M8** | 多 Agent（§4.8）、TS SDK、管理 API（§4.7） | 单流 agent_id；SDK 一轮；admin 鉴权 |
| **M9** | 多机 | 双实例互斥与限流 |
| **M10** | Eval、策略包版本、合规导出 | CI Eval；回滚；导出 |
| **M11** | 多知识后端（平台库、摄取、外部检索） | 实现已合入，待真实环境与发布验收 |
| **M12** | AI 控制台（总览、工具、提示词、用量、知识） | 实现已合入，待 Web 与权限发布验收 |

**对外版本（写死）**：

| 标签 | 含义 |
|------|------|
| **v0.1.0** | 技术预览：现有能力可体验；P1 参考案例与 P2 生产验证尚未完成，不承诺生产稳定或默认多机 |
| **v1.0** | **M0–M4 全部验收通过**（单机主承诺）；不含必须 M5+ |
| v1.x | 叠加已交付的 M5–M8 |
| v1.x+M9 | 多机 |
| v2.0 | M10 平台完备 |
| v2.1（目标） | M11 + M12 发布验收通过；版本是否发布取决于 P1/P2，而非仅代码合入 |

品牌重命名与里程碑互不影响、可单独安排；CLI/包名切换单列任务，文档在未改名前写清别名。

---

## 十二、Port 全景

| Port | 产品线 | 职责 |
|------|--------|------|
| RunContext | 内核 | §4.1 |
| EventLog | 内核 | §4.2 / §5.3 |
| PolicyEngine | 内核 | §4.3 |
| LLMGateway | 内核 | §5.2 |
| Pipeline 插件 | 内核 | §3.3 |
| MessageStore / RunStore | A | 投影与 run 状态 |
| 已有编排 Ports | A | Lock/Cancel/Runtime/Checkpointer/Sink/Hooks |
| ContextManager / MemoryStore / Retriever | B | 知识 |
| DataSource / DataFilter / DataMasker / ToolExecutor / ApprovalGate / OutputGovernor / InputValidator / AuditLogger / MetricsCollector | C | 治理 |
| ConfigProvider / PromptRegistry / AgentOrchestrator | D | 协作 |
| RateLimiter | C | 或仅 middleware |

每个 Port：Protocol + noop/fake + 真实 adapter；只在服务启动时的组装代码 `new`。

---

## 十三、风险与原则

### 13.1 风险

| 风险 | 缓解 |
|------|------|
| 内核耦合 | 三件套边界；产品线经 Port |
| EventLog 体积 | 全量已提交保留；TTL/冷归档；在线读走投影表 |
| append 与推送不一致 | append-before-emit；失败终止 |
| 审批占锁死会话 | §4.6 默认释放锁 |
| 策略误放行 | deny-by-default；矩阵测试 |
| Gateway 一刀切改域 | `LLM_BACKEND` 过渡 |
| 可逆脱敏泄漏 | run 作用域；日志禁原文 |
| 多 Agent 流混乱 | 单流 + `agent_id` |
| 管理面越权 | §4.7 |

### 13.2 设计原则

| 原则 | 说明 |
|------|------|
| 以已经写入成功的事件为准 | 投影可重建；未提交不算数 |
| 策略按 action | 避免 mask/deny 混用 |
| Gateway 可过渡 | 再唯一出口 |
| 租户硬隔离 | Port + checkpointer 键 |
| 审批不占死锁 | 默认释放 + awaiting 状态 |
| 不可用 tool 不暴露 | list + invoke 双检 |
| 渐进 extras | 未装即 noop |
| 官方示例驱动 | 每线可演示 |
| 诚实边界 | 矩阵、弱项、命名 |

---

## 附录 A：相对 v3 / v2

| 来自 | 保留 | 升级 |
|------|------|------|
| v3 | 注入纪律、middleware/Pipeline 分离、extras、单机诚实 | 平台愿景 |
| v2 | 权限/脱敏/RAG/人机灵感 | 四条产品线 + 三件套 |
| v4 | 愿景与里程碑骨架 | v4.1 钉死审阅空洞 |

## 附录 B：弱项

- 无官方托管与 Studio  
- 多 Agent = subgraph 委托，非研究型 GroupChat  
- 多机仅 M9；默认单机  
- 包名：`agentbridge_*` / PyPI：`agentbridge-core`  
- 合规认证需项目侧补齐  

## 附录 C：v4.1 / v4.1.1 修订摘要

### v4.1

1. EventLog = 已提交事件；**append-before-emit**；澄清与断连关系  
2. 总图改为 Lifecycle 内调用 Gateway/Policy/emit  
3. RunContext **两阶段**；checkpointer `{tenant}::{thread}`  
4. Policy **按 action** 表  
5. **HIL 与锁**：等待时释放锁、同 run_id resume、超时 deny  
6. Gateway **`LLM_BACKEND` 过渡**  
7. 管理面鉴权、多 Agent 单流、出口治理边界、EventLog 保留  
8. M2 拆 **M2a/M2b**；**v1.0 = M0–M4**  
9. Metrics/OTel 改为执行期打点，不强制 EventLog 投影  

### v4.1.1（与 Plan r2 对齐）

1. EventLog **全量**已提交事件；MessageStore **合并** text_delta（钉死）  
2. M2a **强制 invoke 双检**；未实现的 action 默认 `deny`  
3. 增加附录 D：五份实施 Plan 映射  
4. DataSource 开关与 memory checkpointer **解耦**（见 database-integration / Plan2）  
5. ThreadLock 在多机下参数为 **storage_key**（与 checkpointer 键同公式，见 Plan5）  
6. **Plan r3**：硬/软依赖矩阵见 `docs/superpowers/plans/DEPENDENCIES.md`；Plan4 硬依赖 Plan1 **RunStore**；Plan1 起锁即用 storage_key  

## 附录 D：实施 Plan 映射

| Plan | 文件 | 里程碑 | 版本 |
|------|------|--------|------|
| 1 可安全接入 | `docs/superpowers/plans/2026-07-24-plan1-secure-access.md` | M1+M2a+M2b | → v0.2 |
| 2 可查库 | `.../2026-07-24-plan2-datasource.md` | M3 | → v0.3 |
| 3 单机生产 | `.../2026-07-24-plan3-single-node-prod.md` | M4 | → **v1.0** |
| 4 智能与治理 | `.../2026-07-24-plan4-intelligence-governance.md` | M5–M7 | → v1.x |
| 5 协作与扩展 | `.../2026-07-24-plan5-collaboration-scale.md` | M8–M10 | → 多机/v2.0 |

索引：`docs/superpowers/plans/README.md`。依赖矩阵：`docs/superpowers/plans/DEPENDENCIES.md`。  
与本文冲突时：**契约以本文 §4 为准，任务切分以 Plan 为准，开工顺序以 DEPENDENCIES 硬/软表为准**。

### 依赖摘要（v4.1.1 / Plan r3）

| 消费 | 必须先完成 | 说明 |
|------|--------|------|
| Plan2 | Plan1 M2a | 可与 Plan1 M2b 并行 |
| Plan3 | Plan1 | Pipeline / 建议含 EventLog |
| Plan4 | Plan1（含 **RunStore**）+ Plan3 | HIL 依赖 RunStore；v1.0 后再称 v1.x |
| Plan5 | Plan1；条件 + Plan4 T4 | Redis 锁键 = Plan1 storage_key |
