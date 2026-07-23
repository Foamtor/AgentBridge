# Agent-Base 后端架构调研

> 日期：2026-07-23  
> 目的：为绿场重写提供依据——对照业界实践与开源项目，选定分层、模式与技术边界  
> 结论已吸收进：[`2026-07-23-agent-ai-base-design.md`](./2026-07-23-agent-ai-base-design.md)

---

## 1. 调研范围

| 维度 | 关注点 |
|------|--------|
| Agent 运行时 | LangGraph vs OpenAI Agents SDK 等 |
| 服务分层 | 整洁/六边形、垂直模块、插件域 |
| 生产能力 | checkpoint、流式、取消、并发、可观测 |
| 门禁 | import 方向强制、测试边界 |
| 开源参照 | 可学结构，禁止照抄实现进本仓 |

产品仓 `RAG_Agent` 只作**能力清单与行为对照**，不作代码母版。

---

## 2. Agent 运行时选型

### 2.1 对比摘要

| | LangGraph | OpenAI Agents SDK |
|--|-----------|-------------------|
| 心智模型 | 显式状态机（节点/边/State） | Agent + Handoff + Guardrail |
| 持久化 | Checkpointer 一等公民（Postgres 等） | Session / 可接 Temporal 等 |
| 流式 | 多 mode（values/updates/messages/custom） | 自有 tracing/流式 |
| 与产品仓 | **已验证**多场景子图、SSE、cancel | 不一致，迁移成本高 |
| 适合 | 多路由业务图、可恢复、HITL | 轻量多 Agent 交接、偏 OpenAI 生态 |

### 2.2 决定

**主运行时：LangGraph（含 LangChain Core 工具协议）。**

理由：与产品仓能力同构；checkpoint + thread/run 模型成熟；本仓要解决的是**宿主与分层**，不是换一套 Agent 框架。

不把 **LangGraph Platform / LangSmith Agent Server** 当作运行依赖：自建 FastAPI 宿主，但**借用其领域词汇与 API 形状**：

| Platform 概念 | 本仓对应 |
|---------------|----------|
| Thread | `thread_id` 会话键 + checkpoint 命名空间 |
| Run | 一次图调用（`run_id`、状态、可取消） |
| Assistant / graph | 注册表中的 `route` → graph builder |
| multitask_strategy=reject | 同 thread 忙 → **409** |
| SSE / stream modes | 自有稳定事件子集（可对照 messages/updates/custom） |

官方流式文档：[Streaming](https://docs.langchain.com/langsmith/streaming)、[Event streaming](https://docs.langchain.com/langsmith/event-streaming)。本仓第一期做**自研精简 SSE 契约**（对齐产品仓调试体验），不实现完整 Platform Protocol v2。

---

## 3. 后端分层：学什么、不学什么

### 3.1 开源/社区参照

| 参照 | 可取 | 不宜照搬 |
|------|------|----------|
| [python-hexagonal-architecture-template](https://github.com/MatthiasEg/python-hexagonal-architecture-template) | **import-linter 强制分层**；内向依赖 | 过重的纯 domain 仪式（Agent 图无法完全脱离框架） |
| [langgraph-agent-clean-architecture](https://github.com/eng-mostafa-alrahal/langgraph-agent-clean-architecture) | `api` / `modules` / `infrastructure` 垂直切分；会话与 orchestration 分模块 | Celery 默认承载对话流、全家桶 RAG/MCP 第一期不进 |
| [fastapi-agent-blueprint](https://github.com/ZachDreamZ/fastapi-agent-blueprint) | 域四层 + worker 边界意识；AGENTS.md 协作 | Admin/MCP/多云适配器超出底座范围 |
| [agentea](https://github.com/kasundularaam/agentea) | Ports + DI 思路 | 绑定特定云 Agent 栈 |
| 生产文实践（PostgresSaver、瘦 State、recursion_limit） | 见 §4 | 博客示例代码不直接入库 |

### 3.2 本仓采用：**分层 + 接口 + 构造注入 + 插件域**（非完整 DDD）

用人话讲（「六边形」只是业界别名，本仓统一用下面说法）：

- **内核**管「一次 Run 怎么跑完、怎么推事件、怎么锁会话」——不写业务问答逻辑。  
- **端口（Ports）**是内核对外依赖的接口：锁、checkpoint、事件出口、跑图、取消、时钟等。  
- **适配器（Adapters）**用具体技术实现端口：LangGraph、Postgres、内存锁、SSE。  
- **域插件**只负责「注册哪张图、哪些工具」；启动时挂上，运行时内核通过注册表调用。

**刻意不做：** 每个小功能都拆 Entity/Repository/UseCase 四件套；用复杂 DI 容器堆生命周期。组装放在 `apps/api` 的 lifespan / composition 即可。

```text
依赖方向（只允许实线方向）

  apps/web ──HTTP──▶ apps/api (delivery / lifespan)
                         │
                         │  lifespan：new adapters，注入 RunLifecycle
                         │  domains.bootstrap → registry.register_*
                         ▼
                   core.application  (RunLifecycle)
                         │ 只依赖 ports + registry + protocol
                         ▼
                      ports（接口）
                         ▲
                         │ 实现
                      adapters（LangGraph / PG / 锁 / SSE）

  domains/* ──register──▶ registry
  domains 可依赖 core 的「公开 API + 图工具类型」
  core 禁止 import domains
  application 禁止 import adapters
```

---

## 4. 生产级 Agent 实践（纳入设计约束）

来源：LangGraph 生产部署/State/Checkpoint 系列实践（2025–2026）。

| 实践 | 本仓约束 |
|------|----------|
| 类型化 State（TypedDict/Pydantic）+ reducer | 域图必须显式 State；消息类字段用 append reducer |
| 生产用 Async Postgres checkpointer，开发可用 Memory | `packages/core` 通过端口切换；compose 默认 PG |
| State 保持精简；大对象外置 | 契约文档写明；scaffold 注释警示 |
| `recursion_limit` / 步数上限 | Run 配置默认带上限 |
| 工具失败不拖垮整图 | 域模板：工具错误转为可流式错误事件 |
| 侧效应节点注意 resume 重入 | 文档要求幂等或 outbox；报告类导出放域 |
| Checkpoint 增长 | 后置：保留策略/清理任务（P7） |
| 可观测 | hooks → 可选 OTel/Langfuse 适配器，核心不绑厂商 |
| HITL interrupt | 第一期不强制；ports 预留，P7 再做 |

---

## 5. 设计模式清单（本仓怎么用）

| 模式 | 用在哪 | 解决什么 |
|------|--------|----------|
| **插件 / 注册表** | GraphRegistry、ToolRegistry | 去掉写死 `if route == ...` 工厂 |
| **端口与适配器** | Checkpointer、EventSink、ThreadLock、Hooks | 内核不绑 FastAPI/PG 细节；可测 |
| **应用服务（用例）** | `RunLifecycle.start_stream` / `cancel` | HTTP 层变薄，行为集中可测 |
| **策略** | RouteResolver（可选） | 路由规则可外置，默认显式 route |
| **观察者 / 钩子** | `on_run_end` 等 | 观测、落库不进核心必选路径 |
| **防腐层** | SSE Event Mapper | LangGraph 内部流 → 稳定对外事件 |
| **脚手架复制** | `domains/_scaffold` | 新域标准形状，避免复制粘贴核心 |

反模式（产品仓已出现、本仓禁止）：

- 核心直接 import 业务包  
- 巨型 God Factory 按 route 分支  
- 在 SSE bridge 里写死业务表写入  
- 「先拷 orchestration 再删」当模板  

---

## 6. 核心领域对象（词汇表）

| 概念 | 含义 |
|------|------|
| **Thread** | 会话标识；checkpoint 与锁的粒度 |
| **Run** | 某 Thread 上一次图执行；有 `run_id`、起止、取消 |
| **Route** | 逻辑场景名；映射到已注册 graph builder（≈ Assistant） |
| **Event** | 对外 SSE 稳定类型（start/delta/tool/…/done/error/cancel） |
| **Domain Plugin** | 一组 tools + graph (+ 可选 input_builder) + bootstrap 注册 |

状态机（Run，简化）：

```text
  accepted → running → completing → succeeded
                 │                      │
                 ├─→ cancelling → cancelled
                 └─→ failed
  busy(thread) → 新请求 409
```

---

## 7. 建议的核心包内部结构（相对初稿加细）

```text
packages/core/src/agent_base_core/
  application/
    run_lifecycle.py      # start_stream / cancel
    errors.py             # ThreadBusy, RunNotFound, …
  ports/
    checkpointer.py
    event_sink.py
    thread_lock.py
    hooks.py
    clock.py
  adapters/
    langgraph_runtime.py  # 编译图、astream、映射
    postgres_checkpointer.py
    memory_checkpointer.py
    inprocess_lock.py
    sse_event_sink.py
  registry/
    graphs.py
    tools.py
  protocol/
    events.py             # 对外事件 schema（Pydantic）
    sse.py                # 序列化
  public.py               # 唯一推荐对外导出面
```

`apps/api`：delivery（路由、鉴权、DTO）+ composition（组装端口实现）+ `domains/`。

门禁：

- **import-linter**：`application` 不依赖 `adapters`；`adapters` 可依赖 ports；domains 互不强制依赖；core 禁止 domains。  
- 另保留简单「禁止业务包名」扫描（防产品仓包名泄漏）。

---

## 8. 与产品仓能力对照（实现策略）

| 产品仓能力 | 本仓策略 |
|------------|----------|
| `orchestration_stream` + SSE | 应用服务 + Event Mapper **重写** |
| thread 锁 / 409 / cancel | ports + Run 状态机 **重写** |
| checkpointer | Postgres 适配器 **重写** |
| 多 skill 图 | 注册表 + echo 示例；业务图不迁代码 |
| OIDC | API/Web **重写**，协议对齐 Authentik |
| 调试台 | React **重写** |
| plan_trace / 点踩表 | 仅 hooks，默认空 |

---

## 9. 技术栈基线（后端）

| 层 | 选择 |
|----|------|
| 语言 | Python 3.12+ |
| HTTP | FastAPI + Uvicorn |
| Agent | LangGraph + langchain-core |
| 校验 | Pydantic v2 |
| DB | PostgreSQL；async checkpointer |
| 鉴权 | OIDC JWT（Authentik） |
| 包管理 | uv（推荐）或 pip；仓内 path 包 |
| 质量 | pytest、ruff、mypy（适度）、import-linter、CI |
| 可观测 | 结构化日志 + hooks；OTel 后置 |

前端调试台：React 18 + TS + Vite（见主设计 §8）。

---

## 10. 调研结论（写入主设计的 ADR 摘要）

1. **LangGraph 自建宿主**，不绑 LangGraph Platform 托管，但采用 Thread/Run/Route 词汇。  
2. **分层 + 接口 + 构造注入**：application + ports + adapters + registry；域为插件。  
3. **import-linter + 测试** 防止结构再次散乱。  
4. **生产约束**（瘦 State、PG checkpoint、recursion_limit、取消/409）写进核心默认行为。  
5. **开源只借鉴结构与门禁，不复制仓库代码。**

---

## 11. 参考链接

- LangGraph Streaming / Event streaming（LangChain docs）  
- Import Linter：https://import-linter.readthedocs.io/  
- Hexagonal FastAPI template（import 门禁）：MatthiasEg/python-hexagonal-architecture-template  
- LangGraph Clean Architecture 示例：eng-mostafa-alrahal/langgraph-agent-clean-architecture  
- OpenAI Agents SDK vs LangGraph 对比文（选型背景）  
- 产品仓文档：`RAG_Agent/docs/Agent技术/05-编排核心提取与可迁移方案.md`（能力边界参考，非实现蓝本）
