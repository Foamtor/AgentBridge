# Agent-Base 全栈 AI 基底模板 — 设计规格

> **阅读提示：** 这是历史设计/实施记录。文中若仍有偏内部的说法，请以仓库根目录 README、docs/roadmap.md、docs/add-a-domain.md 的白话为准。\n\n> **历史规格。** 当前产品总说明：[00-AgentBridge完整方案.md](../../00-AgentBridge完整方案.md) **v4.1**；冲突时以 v4.1 为准。  
> 状态：**审阅高优项已修复**（见 §19）；可写实施计划；P0 待填 contracts JSON 样例  
> 日期：2026-07-23  
> 仓库：`D:\WorkSpace\code\project\Agent-Base`（模板仓，绿场）  
> 参照产品仓：`D:\WorkSpace\code\project\RAG_Agent`（继续演进，不整包拷贝）  
> 架构必读：[OO 分层说明](./2026-07-23-backend-oop-architecture.md)  
> 代码结构：[完整目录树](./2026-07-23-code-structure.md)  
> 调研附录：[后端架构调研](./2026-07-23-backend-architecture-research.md)  
> 契约骨架：[docs/contracts.md](../../contracts.md)

---

## 1. 结论

本仓库是**可复用的 AI 业务本平台模板**：鉴权、部署、编排内核、React 调试台、业务插件模型一步到位。

| 原则 | 含义 |
|------|------|
| 双仓 | 产品仓继续做业务；本仓做干净本平台 |
| 绿场重写 | 对照产品仓的**能力与行为**重新设计实现，禁止大段照抄现网散乱代码 |
| 契约对齐 | SSE / 取消 / 同会话锁 / OIDC 等对外行为可验收对照；内部结构全新 |
| 完整目标 | 不做「先凑合最小交付」；用分阶段任务落地同一完整目标态 |
| 务实分层 | 接入层 / 应用服务 / 接口(ports) / 实现(adapters) / 注册表；**构造注入**；[OO 说明](./2026-07-23-backend-oop-architecture.md) |
| LangGraph 自建宿主 | 运行时用 LangGraph；不绑 Platform 托管，但采用 Thread/Run/Route 词汇 |

一句话：

> 产品仓证明「业务里 AI 要什么」；本仓用业界可维护的后端结构决定「怎么写」。

---

## 2. 背景与动机

产品仓 `RAG_Agent` 已验证：统一流式入口、SSE、同 thread 排队/取消、checkpointer、多场景子图、Authentik OIDC、前端联调。

同时存在：

- 编排与业务插件耦合（工厂写死路由、工具表绑死本仓、核心 import 业务包）
- 目录与职责随历史堆叠，结构散乱，不适合直接当「下一个项目的母版」
- 整仓当模板会拖入一张图、地图工具、入库 worker 等产品债

因此需要独立模板仓，且**重构重写**，而不是净化拷贝。

产品仓已有方案稿（编排提取、不做 SDK）可作为「要抽哪些能力」的参考；本仓不沿用其「整目录拷贝 orchestration」的落地方式。

---

## 3. 目标与非目标

### 3.1 目标

| ID | 目标 | 可验证 |
|----|------|--------|
| G1 | 完整本平台可独立启动 | compose + API + React 调试台 +（可选）Authentik |
| G2 | 编排内核结构清晰、可测 | 分层明确；核心零业务插件 import；注册表注入图与工具 |
| G3 | 新业务只加业务插件、不改内核 | 复制 scaffold → register → 调试台选 route 可见 SSE |
| G4 | 鉴权可开关 | `AUTH_REQUIRED=false` 本地免登录；true 时 Bearer JWT |
| G5 | 与产品仓行为可对照 | 契约清单上的流式生命周期、409、cancel 在本仓复现 |
| G6 | 代码质量验收条件 | lint/测试/核心 import 扫描；禁止向核心塞场景 |

### 3.2 非目标

- 不把产品仓业务插件（地图、政策图谱、报告产品逻辑、一张图前端）打进默认模板
- 不把现网 `orchestration/`、`ai_map_chat/`、Streamlit 调试台大段粘贴过来
- 第一期不发强制语义化版本的内部 pip SDK（可用仓内 path 包；发包后置）
- 第一期不强制产品仓迁移到本核心（双轨；稳定后再议）
- 不绑产品仓现网 K8s/集群细节；生产只给通用部署说明
- 默认不包含 ingest / policy-extract worker 实现（可留 compose profile 占位说明）

---

## 4. 双仓关系

```text
RAG_Agent（产品仓）                    Agent-Base（本仓）
继续演进业务                            绿场本平台权威说明
        │                                      ▲
        │  提供：能力清单、验收场景、踩坑经验     │
        └──────── 契约 / 对照用例 ──────────────┘
                        │
                        │  不提供：散乱实现照搬
                        ▼
                 未来新业务项目 A/B
                 clone 本仓 → 写自己的 domains
```

| | 产品仓 | 本仓 |
|--|--------|------|
| 职责 | 乡村产业 MAP 等业务 | AI 业务通用本平台 |
| 代码 | 历史实现继续维护 | 全新分层与实现 |
| 前期同步 | 契约与验收期望 | 实现真相 |
| 后期（可选） | 接入本仓核心包或保持分叉 | 本平台稳定后可考虑内部包 |

---

## 5. 架构决策（ADR）

详细论证见[调研文档](./2026-07-23-backend-architecture-research.md)。此处只保留决定。

| ID | 决策 | 选择 | 不选 / 备注 |
|----|------|------|-------------|
| ADR-1 | Agent 运行时 | **LangGraph** + langchain-core | 不用 OpenAI Agents SDK 作主运行时（与产品能力同构成本高） |
| ADR-2 | 部署形态 | **自建 FastAPI 宿主** | 不依赖 LangGraph Platform / LangSmith Agent Server 托管 |
| ADR-3 | 领域词汇 | Thread / Run / Route（对齐 Platform 概念） | 第一期不实现完整 Platform Protocol v2 |
| ADR-4 | 分层风格 | **分层 + 接口 + 构造注入**（目录名 ports/adapters = 接口/实现） | 不做每域完整 DDD；详见 [OO 架构说明](./2026-07-23-backend-oop-architecture.md) |
| ADR-5 | 扩展模型 | **业务插件 + 注册表** | 禁止核心写死 `if route == ...` |
| ADR-6 | 持久化 | 生产 **Async Postgres** checkpointer；开发可 Memory | 不用 SQLite 当生产默认 |
| ADR-7 | 边界验收条件 | **import-linter** + 业务包名扫描 | 仅靠约定不够 |
| ADR-8 | 可观测 | Hooks 端口；可选 OTel/Langfuse 适配器后置 | 核心不绑厂商 SDK |
| ADR-9 | 长任务 | 对话流式走请求内 Run；重 worker 后置 | 第一期不上 Celery/Taskiq 默认路径 |
| ADR-10 | 开源用法 | 只借鉴结构与验收条件 | **禁止**把参照仓库代码粘进本仓 |

### 5.1 采用的设计模式

| 模式 | 用途 |
|------|------|
| 插件 / 注册表 | 图与工具按 route 注入 |
| 端口与适配器 | ThreadLock、EventSink、Checkpointer、GraphRuntime、RunCancelRegistry、Hooks |
| 应用服务 | `RunLifecycle`：加锁 → 建 Run → 推流 → 释放；`cancel` |
| 防腐层 | LangGraph 内部流 → 稳定对外 SSE 事件 |
| 策略（可选） | RouteResolver；默认请求显式带 route |
| 观察者 | 生命周期 hooks |

### 5.2 核心对象

- **Thread**：会话键；锁与 checkpoint 粒度  
- **Run**：一次图执行（`run_id`、可取消、状态机）  
- **Route**：注册表中的图名（≈ Assistant）  
- **Event**：对外稳定 SSE 类型  
- **Domain Plugin**：tools + graph + bootstrap  

Run 简化状态：`accepted → running → succeeded | failed | cancelled`；thread 忙则新请求 **409**。

**后端类怎么拆、接口怎么注入：** 见 [后端代码架构说明（面向对象视角）](./2026-07-23-backend-oop-architecture.md)（必读）。

---

## 6. 目标目录结构

**完整到文件级的树与职责表：** 见 [代码结构设计](./2026-07-23-code-structure.md)（以该文为准；仓库骨架已按此落库）。

摘要：

```text
packages/core/src/agent_base_core/   # application · ports · adapters · registry · protocol
apps/api/                            # main · lifespan(服务启动时的组装代码) · auth · routes · domains
apps/web/src/                        # features/auth|debug|contracts · lib/sseClient
```

依赖方向（强制，由 import-linter 检查）：

```text
apps/web ──HTTP──▶ apps/api (delivery / lifespan)
                      │
                      │  lifespan：new adapters，注入 RunLifecycle
                      │  domains.bootstrap → registry.register_*
                      ▼
              agent_base_core.application  (RunLifecycle)
                      │ 只依赖 ports + registry + protocol
                      ▼
                   ports（接口）
                      ▲
                      │ 实现
                   adapters（LangGraph / PG / 锁 / SSE）

禁止：
  application → adapters
  core → domains / 产品业务包名
  域之间默认互不依赖（除非显式共享库）
```

---

## 7. 运行时架构

```text
React 调试台
  │  OIDC PKCE → Authentik（可关）
  │  Authorization: Bearer
  ▼
FastAPI delivery（routes / auth）
  │  DTO → RunLifecycle.start_stream / cancel
  ▼
application.RunLifecycle
  │  ThreadLock.acquire（忙 → 409）
  │  创建 Run、解析 Registry
  │  GraphRuntime.astream → EventSink → SSE
  │  Hooks；释放锁
  ▼
adapters（LangGraph + Checkpointer）
  ▲
domains/* 仅通过 Registry 挂接
```

生产默认约束（进核心行为，不只写文档）：

- 类型化 Graph State + 消息类 reducer  
- `recursion_limit` 默认上限  
- State 保持精简（大对象外置，scaffold 注释说明）  
- 工具错误转为可流式 error/tool_result，避免无处理异常打崩 Run  

---

## 8. 稳定契约（文档契约；实现全新）

### 8.1 流式入口（语义）

宿主应调用应用层（对外也可经 `public.orchestration_stream` 薄封装），至少包含：

- `query`、`thread_id`、已解析的 `route`
- 可选 `input_state` / 已注册的 input_builder
- 可选 `configurable_extra`
- 返回 SSE 流（FastAPI `StreamingResponse` 由 delivery 适配）

核心**不**根据业务 `source_module` 写死工具列表。

### 8.2 注册

```text
register_graph(route, builder)
register_tools(key, tools)
register_input_builder(route, fn)   # 可选
```

新场景只改域的 bootstrap，不改 stream 入口。

### 8.3 SSE 事件子集（稳定）

通用：`start` / `step_update` / `text_delta` / `tool_call` / `tool_result` / `done` / `error` / `cancel_requested` / `cancelled`

域扩展事件由域节点发出；核心原样透传，不解析业务字段。

字段级 JSON 形状在 `docs/contracts.md` 定稿，并与产品仓做对照表（允许命名微调，但须在 parity 文档写明）。

### 8.4 运行时行为

- 同 `thread_id` 已有进行中的 run → **409**
- 支持 cancel → 发出取消相关事件并结束
- checkpointer 可持久化对话状态（Postgres）

### 8.5 Hooks（可选）

```text
on_run_end(payload)
on_sql_turn(payload)     # 若域需要
on_feedback(payload)     # 点踩等；默认不实现
```

### 8.6 鉴权

- Authentik OIDC；API 校验 Bearer JWT
- `AUTH_REQUIRED=false` 时跳过（本地开发）
- Web：授权码 + PKCE；callback 路由

---

## 9. React 调试台（完整能力）

唯一官方调试前端（不包含 Streamlit、不包含一张图）。

| 能力 | 说明 |
|------|------|
| 登录 | OIDC 登录/退出；可选手动 Token |
| 会话 | 新建/复用 `thread_id`；演示 409 |
| 发送 | query、route（默认 echo）、可选 model / extra JSON |
| 时间线 | SSE 事件列表、类型着色、展开 raw、复制 |
| 控制 | Cancel、清空时间线 |
| 契约页 | `/contracts` 列出事件与示例 payload |

技术栈：React 18 + TypeScript + Vite；UI 可用 Ant Design，但零地图/业务大盘依赖。  
PKCE 与 SSE 客户端：**重写**，只对齐 Authentik 与契约行为。

---

## 10. 鉴权与部署

| 组件 | 形态 |
|------|------|
| Postgres | 业务库 + checkpointer；Authentik 可用同实例不同 database |
| Redis | Authentik 依赖 |
| Authentik | compose 服务 + 初始化说明（application、redirect URI） |
| 一键开发 | `start-dev` 起 API + Web；依赖用 compose |
| Worker | 默认不启业务 worker；compose 可用 profile 占位 |
| 生产 | `docs/deploy.md`：镜像、环境变量、反代、OIDC 回调 |

---

## 11. 质量与架构约束（防再散乱）

1. **分层**：delivery / application / ports / adapters / domains；细节见 `architecture.md` 与 ADR。  
2. **import-linter**：CI 强制依赖方向（见 §6）；失败即拒。  
3. **核心公共 API 面小**：优先经 `public.py` 导出；文档白名单。  
4. **禁止**在核心用 `if route == "xxx"` 堆积场景。  
5. **CI（当前已落地）**：import-linter + 业务包名扫描 + api 可安装/import 冒烟。  
   **后续补齐（P2/P3）**：pytest、ruff、echo SSE smoke。  
6. **业务插件内聚**：工具说明书、handler、子图同域目录。  
7. **不照抄验收条件**：评审拒绝整文件复制产品仓 `orchestration/` 或参照开源仓库实现。  
8. **生产默认**：recursion_limit、瘦 State 指引、工具错误可流式上报。

技术栈基线：Python 3.12+、FastAPI、LangGraph、Pydantic v2、Postgres、uv（推荐）、Authentik OIDC。

---

## 12. 明确不进默认树

- 产品仓一张图 / OpenLayers / Deck.gl / 产业大盘 UI  
- `ai_map_chat` 及地图工具实现  
- ingest / policy-extract 业务 worker 实现  
- Streamlit  
- 产品点踩表、plan_trace 表结构（仅 hooks）  
- LangGraph Platform 托管依赖、完整 Protocol v2  
- 默认 Celery/Taskiq 对话路径、Admin UI、第一期 MCP 服务器  

需要时在 `docs/parity-with-product.md` 说明「如何从产品仓理解某域后，在本仓新建等价域」，而不是拷目录。

---

## 13. 分阶段任务（完整目标的实施顺序）

阶段是落地顺序，每阶段完成标准都是完整目标的一块，而不是临时凑合。

### P0 — 契约冻结

| 任务 | 内容 | 完成标准 | 状态 |
|------|------|----------|------|
| P0.1 | 从产品仓整理能力与验收场景 | `docs/contracts.md` 有字段级 JSON | **已完成** |
| P0.2 | SSE / 409 / cancel / 鉴权对照表 | `docs/parity-with-product.md` 初稿 | **已完成** |
| P0.3 | 公开 API、Event schema、import-linter | `.importlinter` 可跑通 | **已完成** |

### P1 — 基建

| 任务 | 内容 | 完成标准 | 状态 |
|------|------|----------|------|
| P1.1 | 目录骨架、README、.gitignore、基础 CI | 空仓可 clone；architecture gates 绿 | **已完成** |
| P1.2 | docker-compose：PG + Redis + Authentik | 容器健康 | **已完成**（Authentik 为 profile，非 smoke 必过） |
| P1.3 | `apps/api` 空壳：health、config、lifespan | `/health` 通 | **已完成** |
| P1.4 | 鉴权中间件 + 开关 | 开关两种模式可测 | **已完成**（HS256/JWKS；stub 仅 `AUTH_DEV_STUB`） |
| P1.5 | start-dev / stop-dev | 文档路径可走通 | **已完成** |

### P2 — 核心重写（分层 + 接口 + 注入）

| 任务 | 内容 | 完成标准 | 状态 |
|------|------|----------|------|
| P2.1 | ports + registry（含 input_builders） | 单测 | **已完成** |
| P2.2 | adapters：inprocess lock、memory/pg checkpointer | 单测含 409 语义 | **已完成** |
| P2.3 | protocol events + SSE sink | 单测 | **已完成** |
| P2.4 | adapters.langgraph_runtime + Event 防腐映射 | 集成测 | **已完成** |
| P2.5 | application.RunLifecycle（stream/cancel） | 与注册表集成测 | **已完成** |
| P2.6 | hooks 默认空；public 导出面（只转发、不 new 适配器） | 可注入示例 | **已完成** |
| P2.7 | import-linter + 业务包名扫描进 CI | 违规失败 | **已完成**（含 pytest/ruff） |

### P3 — echo 域

| 任务 | 内容 | 完成标准 | 状态 |
|------|------|----------|------|
| P3.1 | echo 工具 + 类型化 State 子图 | 注册成功 | **已完成** |
| P3.2 | API delivery 挂 stream/cancel | HTTP 层通 | **已完成** |
| P3.3 | 自动化：SSE 生命周期、409、cancel | CI 绿 | **已完成** |

### P4 — React 调试台

| 任务 | 内容 | 完成标准 | 状态 |
|------|------|----------|------|
| P4.1 | Vite/React 工程与 env 契约 | 可 dev | **已完成** |
| P4.2 | 重写 auth PKCE + callback | 与 Authentik 联调 | **部分**（手动 Bearer；PKCE 占位） |
| P4.3 | 重写 sseClient | 覆盖稳定事件子集 | **已完成** |
| P4.4 | Debug 工作台全功能 | 登录/thread/发送/时间线/cancel/409 | **已完成**（登录=粘贴 token） |
| P4.5 | `/contracts` 页 | 与 docs 一致 | **已完成** |
| P4.6 | smoke 脚本端到端 | 文档一步可跑 | **已完成** |

### P5 — 脚手架与文档

| 任务 | 内容 | 完成标准 | 状态 |
|------|------|----------|------|
| P5.1 | `domains/_scaffold`（含 State/recursion 注释） | 复制即可改 | **已完成** |
| P5.2 | add-a-domain / architecture / deploy | 文档齐全 | **已完成** |
| P5.3 | hooks 示例（日志级） | 可插拔证明 | **已完成** |
| P5.4 | （可选）protocol Plan/ToolSpec | 纯结构 + 文档 | **可选未做** |

### P6 — 对照验收与收口

| 任务 | 内容 | 完成标准 | 状态 |
|------|------|----------|------|
| P6.1 | 按 parity 清单在本仓跑通 | 差异有记录 | **已完成** |
| P6.2 | 用 scaffold 做一次「假业务」试挂 | 不改 core | **文档指引完成**（不强制提交假域） |
| P6.3 | README「从零到绿」走查 | 陌生人可跟做 | **已完成** |
| P6.4 | 产品仓侧仅文档互链（可选） | 指向本仓地址与原则 | **可选未做** |

### P7 — 后置（不阻塞模板宣布可用）

| 任务 | 内容 |
|------|------|
| P7.1 | 内部 pip 包与版本策略 |
| P7.2 | 产品仓是否迁到同一核心 |
| P7.3 | Checkpoint TTL/清理；OTel/Langfuse 适配器 |
| P7.4 | HITL interrupt；可选 Platform 协议对齐 |
| P7.5 | 异步 worker 路径（长任务，非默认聊天） |

---

## 14. 成功标准（总验收）

- [x] compose + API + React 调试台 + OIDC（可关）+ echo 全通  
- [x] 同 thread 409、cancel、SSE 稳定事件子集符合 `contracts.md`  
- [x] `packages/core` 通过 import-linter；无域/业务包泄漏  
- [x] 新业务插件仅通过 register + scaffold，无需改核心源码（runtime 映射不硬编码业务节点名）  
- [x] 实现未大段复制产品仓或参照开源仓库代码  
- [x] 文档：architecture、contracts、add-a-domain、deploy、parity、调研附录齐全  
- [x] CI：architecture gates + pytest/ruff  
- [x] ADR-1～10 与实现一致（抽查目录与依赖方向）  
- [ ] P4.2 完整 PKCE ↔ Authentik 联调（后置增强，可用手动 Bearer）  

---

## 15. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 重写偏离现网可用行为 | P0 契约 + P6 parity；关键路径先写验收测试再写实现 |
| 分层过度设计拖慢进度 | ADR-4：只拆 application/ports/adapters，不做每域 DDD |
| 范围膨胀（产品域/MCP/Platform） | 非目标与 §12；评审拒绝 |
| 双仓长期行为漂移 | parity 文档；后期再议单一核心包 |
| 鉴权/Compose 难启动 | `.env.example` + start-dev + AUTH_REQUIRED 开关 |
| 「参考」滑向照抄 | ADR-10 + 评审规则 |
| Checkpoint/State 膨胀 | 瘦 State 约束；P7 TTL |
| 多 API 副本时进程内锁失效 | 第一期默认单副本；多副本需 Redis/PG 锁适配器（P7） |
| cancel 与 stream 协作不清 | ports 含 `RunCancelRegistry`；P2 与产品 cancel 对照 |

---

## 16. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-07-23 | 初稿：双仓、绿场重写、React 调试台、P0–P7 |
| 2026-07-23 | 并入架构调研：ADR、分层、模式清单、import-linter、LangGraph 自建宿主、细化 P2 |
| 2026-07-23 | 增补 OO 视角架构说明（封装/接口/注入/注册表） |
| 2026-07-23 | 内部审阅：补 Cancel 端口、多副本锁风险、GraphRuntime 归 ports |
| 2026-07-23 | 完整代码结构设计定稿并落库骨架（见 code-structure.md） |
| 2026-07-23 | 按第二轮审阅修复：依赖图、api 包装、阶段回写、input_builders、core 依赖、contracts 骨架 |

---

## 17. 下一步

1. 按 [实施计划](../plans/2026-07-23-agent-ai-base-implementation.md) 从 **Task 1**（protocol events）开始实现。  
2. 已完成项见计划「Already done」与 §13 状态列。  
3. P7 后置，不阻塞模板宣布可用。

---

## 18. 内部审阅记录（2026-07-23）

### 结论

**可以进入实施计划阶段。** 目标、双仓、绿场重写、分层+注入、阶段划分一致。

### 已通过

- 原则清晰：行为对齐产品仓、代码不照抄  
- ADR 可执行；OO 文档把封装/接口/注入讲清楚  
- Cursor 规则与目录锚点一致，正反例可用  
- 非目标挡住范围膨胀（地图/Platform/Celery 默认路径）

### 审阅中已修补

- `GraphRuntime` / `RunCancelRegistry` 明确为 ports  
- 风险表补充：多副本进程内锁、cancel 协作  
- OO 示意笔误修正  

### Cursor 规则

`.cursor/rules/python-backend-structure.mdc`：**通过**。保持 `globs: **/*.py` 即可。

---

## 19. Spec 第二轮审阅与修复（2026-07-23）

### 结论

**高优项已修复；规格可通过并写 plan。** 剩余主要是 P0 字段级 JSON（实现前填）。

### 已修复

| ID | 处理 |
|----|------|
| R2-1 | 主设计 §6、调研 §3.2 依赖图改为：lifespan 注入；application 只依赖 ports |
| R2-2 | `apps/api` 增加 hatchling + 显式 packages/force-include；CI 可 `pip install -e` |
| R2-3 | §13 阶段表回写完成度；§11 CI 表述与现状对齐 |
| R2-4 | 保留 `register_input_builder`；新增 `registry/input_builders.py` |
| R2-5 | §5.1 端口表补全 GraphRuntime / RunCancelRegistry 等 |
| R2-6 | `langgraph` / `langchain-core` / `pydantic` 移入 `packages/core`；api 只保留 HTTP/鉴权 |
| R2-7 | P2 标题与调研用语统一为「分层 + 接口 + 注入」 |
| R2-8 | `docs/contracts.md` 改为可填骨架（HTTP/SSE/鉴权/门面约定） |

### 仍待实现（见实施计划，不挡规格通过）

- 按 plan Task 1 起填实代码  
- 前端 `.cursor` 规则（可后补）  
- P7 后置能力

