# Agent-Base 完整代码结构设计

> **阅读提示：** 这是历史设计/实施记录。文中若仍有偏内部的说法，请以仓库根目录 README、docs/roadmap.md、docs/add-a-domain.md 的白话为准。\n\n> 日期：2026-07-23  
> 状态：结构定稿（目录骨架已落库；业务逻辑未实现）  
> 配套：[主设计](./2026-07-23-agent-ai-base-design.md) · [OO 分层](./2026-07-23-backend-oop-architecture.md)

本文给出**每一个目录与文件的职责**。实现按此树生长，禁止另起一套散乱路径。

---

## 1. 总原则

| # | 原则 |
|---|------|
| 1 | 仓库是 **monorepo**：`packages/*` 可复用库，`apps/*` 可运行应用 |
| 2 | Python 包用 **src layout**（`packages/core/src/agent_base_core`） |
| 3 | 业务按 **domains 插件** 扩展；跨域能力进 `agent_base_core` |
| 4 | 一个文件一类主责；组装只在 `apps/api/lifespan.py` |
| 5 | 测试镜像源码树：`packages/core/tests/`、`apps/api/tests/` |

---

## 2. 完整目录树

```text
Agent-Base/
├── .cursor/
│   └── rules/
│       └── python-backend-structure.mdc
├── .github/
│   └── workflows/
│       └── ci.yml                          # 后置：ruff/pytest/import-linter/smoke
├── .env.example
├── .gitignore
├── .importlinter                           # 核心分层契约
├── README.md
├── docker-compose.yml                      # PG + Redis + Authentik
├── start-dev.ps1
├── start-dev.sh
├── stop-dev.ps1
├── stop-dev.sh
│
├── packages/
│   └── core/                               # 编排内核（path 依赖）
│       ├── pyproject.toml
│       ├── README.md
│       ├── src/
│       │   └── agent_base_core/
│       │       ├── __init__.py             # 版本号；不 re-export 一切
│       │       ├── public.py               # 对外薄门面（orchestration_stream 等）
│       │       ├── application/
│       │       │   ├── __init__.py
│       │       │   ├── run_lifecycle.py    # RunLifecycle 应用服务
│       │       │   └── errors.py           # ThreadBusy, UnknownRoute, …
│       │       ├── ports/
│       │       │   ├── __init__.py
│       │       │   ├── thread_lock.py      # Protocol ThreadLock
│       │       │   ├── event_sink.py       # Protocol EventSink
│       │       │   ├── checkpointer.py     # Protocol CheckpointerFactory
│       │       │   ├── graph_runtime.py    # Protocol GraphRuntime
│       │       │   ├── run_control.py      # Protocol RunCancelRegistry
│       │       │   ├── hooks.py            # Protocol RunHooks
│       │       │   └── clock.py            # Protocol Clock（可选，便于测）
│       │       ├── adapters/
│       │       │   ├── __init__.py
│       │       │   ├── inprocess_lock.py
│       │       │   ├── inprocess_cancel.py
│       │       │   ├── memory_checkpointer.py
│       │       │   ├── postgres_checkpointer.py
│       │       │   ├── langgraph_runtime.py
│       │       │   ├── sse_event_sink.py
│       │       │   ├── event_mapper.py     # LangGraph chunk → OutboundEvent
│       │       │   └── noop_hooks.py
│       │       ├── registry/
│       │       │   ├── __init__.py
│       │       │   ├── graphs.py           # GraphRegistry
│       │       │   ├── tools.py            # ToolRegistry
│       │       │   └── input_builders.py   # InputBuilderRegistry（可选）
│       │       ├── protocol/
│       │       │   ├── __init__.py
│       │       │   ├── events.py           # OutboundEvent 及子类型（Pydantic）
│       │       │   ├── sse.py              # event → SSE 字节/行
│       │       │   └── plan_spec.py        # 可选：ToolSpec/Plan 纯结构
│       │       └── templates/
│       │           ├── __init__.py
│       │           └── README.md           # 空壳图说明（无业务）
│       └── tests/
│           ├── conftest.py
│           ├── application/
│           │   └── test_run_lifecycle.py
│           ├── adapters/
│           │   ├── test_inprocess_lock.py
│           │   └── test_event_mapper.py
│           ├── registry/
│           │   └── test_registries.py
│           └── protocol/
│               └── test_sse.py
│
├── apps/
│   ├── api/                                # FastAPI 宿主
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   ├── main.py                         # create_app()
│   │   ├── lifespan.py                     # Composition Root（注入）
│   │   ├── deps.py                         # FastAPI Depends：取 lifecycle
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── middleware.py               # Bearer JWT / AUTH_REQUIRED
│   │   │   ├── oidc.py                     # 校验逻辑
│   │   │   └── schemas.py                  # 可选用户上下文
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── health.py
│   │   │   ├── chat.py                     # /chat/stream /chat/cancel
│   │   │   └── schemas.py                  # ChatRequest 等 HTTP DTO
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   ├── settings.py                 # pydantic-settings
│   │   │   └── logging.py
│   │   ├── migrations/
│   │   │   ├── README.md
│   │   │   └── 001_checkpointer.sql         # 或 Alembic（实现期定）
│   │   ├── domains/
│   │   │   ├── __init__.py
│   │   │   ├── bootstrap.py                # register_all(graphs, tools)
│   │   │   ├── echo/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── bootstrap.py
│   │   │   │   ├── graph.py                # build_echo_graph
│   │   │   │   ├── tools.py
│   │   │   │   ├── state.py                # Typed state
│   │   │   │   └── README.md
│   │   │   └── _scaffold/
│   │   │       ├── __init__.py
│   │   │       ├── bootstrap.py
│   │   │       ├── graph.py
│   │   │       ├── tools.py
│   │   │       ├── state.py
│   │   │       └── README.md               # 复制改名即用
│   │   └── tests/
│   │       ├── conftest.py
│   │       ├── test_health.py
│   │       ├── test_chat_stream.py
│   │       ├── test_chat_cancel.py
│   │       └── test_auth_optional.py
│   │
│   └── web/                                # React 调试台
│       ├── package.json
│       ├── pnpm-lock.yaml                  # 实现时生成
│       ├── vite.config.ts
│       ├── tsconfig.json
│       ├── index.html
│       ├── .env.example
│       ├── README.md
│       └── src/
│           ├── main.tsx
│           ├── App.tsx
│           ├── vite-env.d.ts
│           ├── features/
│           │   ├── auth/
│           │   │   ├── pkce.ts
│           │   │   ├── token.ts
│           │   │   └── callback.tsx
│           │   ├── debug/
│           │   │   ├── DebugPage.tsx
│           │   │   ├── EventTimeline.tsx
│           │   │   ├── SessionBar.tsx
│           │   │   └── SendPanel.tsx
│           │   └── contracts/
│           │       └── ContractsPage.tsx
│           ├── lib/
│           │   ├── apiBase.ts
│           │   └── sseClient.ts
│           └── routes/
│               └── index.tsx
│
├── infra/
│   ├── README.md
│   └── authentik/
│       └── README.md                       # 应用创建、redirect URI 说明
│
├── scripts/
│   ├── import_scan_core.py                 # 业务包名黑名单
│   ├── smoke_echo.ps1
│   └── smoke_echo.sh
│
└── docs/
    ├── architecture.md                     # 指向本结构 + OO
    ├── contracts.md                        # P0：SSE/鉴权契约
    ├── add-a-domain.md
    ├── deploy.md
    ├── parity-with-product.md
    └── superpowers/
        ├── specs/
        │   ├── 2026-07-23-agent-ai-base-design.md
        │   ├── 2026-07-23-backend-architecture-research.md
        │   ├── 2026-07-23-backend-oop-architecture.md
        │   └── 2026-07-23-code-structure.md   # 本文
        └── plans/
```

---

## 3. 模块 → 类 / 函数职责表

### 3.1 `agent_base_core`（内核）

| 文件 | 主类型 / 符号 | 职责 |
|------|----------------|------|
| `public.py` | `orchestration_stream`, `cancel_run` | 给宿主用的稳定门面；**只转发** `RunLifecycle`，禁止在此 new 适配器 |
| `application/run_lifecycle.py` | `RunLifecycle` | 用例：加锁、登记 cancel、跑图、推事件、释放 |
| `application/errors.py` | `ThreadBusy`, `UnknownRoute`, `RunNotFound` | 领域/应用错误；路由层映射 HTTP |
| `ports/*.py` | 各 `Protocol` | 能力抽象，无实现 |
| `adapters/inprocess_lock.py` | `InProcessThreadLock` | 单进程 thread 互斥 |
| `adapters/inprocess_cancel.py` | `InProcessCancelRegistry` | 单进程取消令牌表 |
| `adapters/memory_checkpointer.py` | `MemoryCheckpointerFactory` | 开发用 |
| `adapters/postgres_checkpointer.py` | `PostgresCheckpointerFactory` | 生产用 Async PG |
| `adapters/langgraph_runtime.py` | `LangGraphRuntime` | 编译图 + `astream` |
| `adapters/event_mapper.py` | `map_chunk_to_event` | 防腐：框架流 → 对外 Event |
| `adapters/sse_event_sink.py` | `SseEventSink` | `Event` → `asyncio.Queue` |
| `adapters/noop_hooks.py` | `NoopHooks` | 默认空钩子 |
| `registry/graphs.py` | `GraphRegistry` | `register` / `get` |
| `registry/tools.py` | `ToolRegistry` | `register` / `get` |
| `registry/input_builders.py` | `InputBuilderRegistry` | 可选：`register_input_builder` / `get` |
| `protocol/events.py` | `OutboundEvent` 及子类 | 稳定事件模型 |
| `protocol/sse.py` | `format_sse`, `iter_sse` | 序列化 |

### 3.2 `apps/api`（宿主）

| 文件 | 职责 |
|------|------|
| `main.py` | `create_app()`：挂路由、中间件、lifespan |
| `lifespan.py` | **唯一**服务启动时的组装代码：new 适配器 → 注入 `RunLifecycle` → `domains.bootstrap` |
| `deps.py` | `get_run_lifecycle(request)` |
| `auth/*` | OIDC JWT；`AUTH_REQUIRED` |
| `routes/health.py` | `GET /health` |
| `routes/chat.py` | `POST /chat/stream`, `POST /chat/cancel` |
| `routes/schemas.py` | HTTP 请求体 |
| `config/settings.py` | 环境变量 |
| `domains/bootstrap.py` | 调用各域 `register` |
| `domains/echo/*` | 示例域：State + tools + graph |
| `domains/_scaffold/*` | 复制模板，默认不注册 |

### 3.3 `apps/web`（调试台）

| 路径 | 职责 |
|------|------|
| `features/auth/*` | PKCE、token、callback |
| `features/debug/*` | 会话、发送、事件时间线、cancel |
| `features/contracts/*` | 契约说明页 |
| `lib/sseClient.ts` | 解析稳定事件子集 |

---

## 4. 依赖与 import 规则（与 `.importlinter` 对齐）

```text
允许：
  apps.api.routes          → agent_base_core.public / application.errors / protocol
  apps.api.lifespan        → agent_base_core.adapters + application + registry + domains.bootstrap
  apps.api.domains.*       → agent_base_core.registry (+ langchain/langgraph 按需)
  agent_base_core.application → agent_base_core.ports + registry + protocol
  agent_base_core.adapters    → agent_base_core.ports + protocol + 第三方
  agent_base_core.adapters.*  → agent_base_core.adapters.*   # 同层允许，但仅白名单边（见 .importlinter independence）

禁止：
  agent_base_core.application → agent_base_core.adapters
  agent_base_core.adapters    → agent_base_core.application
  agent_base_core.*           → apps.api.domains.*
  apps.api.domains.echo       → apps.api.domains.<other>   # 域默认互不依赖
  adapters 网状互引（除已批准：langgraph_runtime → event_mapper）
```

业务包名黑名单（`scripts/import_scan_core.py`）：`ai_map_chat`, `app_ai_chat`, `knowlede` 等产品仓包名不得出现在 `packages/core`。

`import-linter` 执行约定（避免 src layout 找包失败）：

- 在仓库根目录执行：`lint-imports`（需先 `pip install -e "packages/core[dev]"`）
- 配置见根目录 `.importlinter`；`containers` 模式下 layers 写相对层名（`application` 而非 `agent_base_core.application`）

---

## 5. 配置与运行入口

| 入口 | 作用 |
|------|------|
| `docker compose up` | PG / Redis / Authentik |
| `uvicorn apps.api.main:app`（或包内约定） | API |
| `pnpm --dir apps/web dev` | 调试台 |
| `start-dev.*` | 一键起 API + Web |

Python 包安装：

- core：`pip install -e "packages/core[dev]"`（运行时含 langgraph；可选 `[postgres]`）
- api：`pip install -e apps/api`（HTTP/鉴权依赖；path 依赖 core）
- langgraph 等 Agent 运行时依赖在 **core**，不在 api 重复声明

---

## 6. 业务插件标准形状

每个域目录固定四件套（scaffold 同构）：

```text
domains/<name>/
  bootstrap.py   # register(graphs, tools)
  state.py       # TypedDict / Pydantic state + reducer 约定
  tools.py       # LangChain tools 列表
  graph.py       # build_<name>_graph(checkpointer, tools, ...) -> compiled
  README.md      # 域说明、route 名
```

`domains/bootstrap.py`：

```python
def register_all(graphs, tools) -> None:
    from apps.api.domains.echo import bootstrap as echo
    echo.register(graphs, tools)
    # 不自动注册 _scaffold
```

---

## 7. 与成熟 FastAPI 结构的对照

| 成熟惯例 | 本仓落点 |
|----------|----------|
| `src/<feature>/router.py` | `apps/api/routes/*` + `domains/<feature>` |
| `service.py` | `agent_base_core.application.RunLifecycle`（跨域用例）+ 业务插件内 graph 节点 |
| `core/config` | `apps/api/config` |
| 按域分包 | `domains/echo`、未来 `domains/xxx` |
| 可复用库抽出 | `packages/core` |

差异原因：编排是**跨域平台能力**，故独立成包，而不是塞进某一个 feature 文件夹。

---

## 8. 骨架落地说明

本仓库已按本文创建**目录与模块占位文件**（模块 docstring 标明职责，无业务逻辑）。  
实现顺序仍遵主设计 P0→P7；占位文件在对应任务中填实，不另开目录。

---

## 9. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-07-23 | 完整代码结构定稿；目录树 + 职责表 + import 规则 |
| 2026-07-23 | 优化：补齐 import-linter 可执行约束与运行约定 |
| 2026-07-23 | 审阅修复：input_builders、core 承载 langgraph、安装约定 |
