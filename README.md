# Agent-Base

**用 LangGraph 做 AI 业务时，可直接 fork 的底座模板。**

它帮你把「流式对话 API、取消、线程锁、SSE 事件契约、域插件」一次搭好，你只往里挂自己的图和工具，而不是每次从零拼 FastAPI + LangGraph + 推流协议。

> 当前定位：**单机模板可用**。默认进程内锁，**不是**开箱即用的多副本生产方案。

---

## 它解决什么问题

做 Agent / RAG / 工具调用类产品时，常见痛点是：

- 每次都要重写：SSE 信封、同会话互斥（409）、取消、鉴权开关
- 业务图和宿主搅在一起，换场景就改内核
- 事件类型随意透传，前后端对不齐

Agent-Base 把这些收成可复用模板：

| 你得到的 | 说明 |
|----------|------|
| 稳定 SSE 契约 | `start` / `text_delta` / `tool_call` / `tool_result` / `done` / `error` / cancel… |
| 扩展事件 | 域自定义 `x.<domain>.*`（有正则校验） |
| 域插件模型 | 新业务只加 `apps/api/domains/<name>`，硬化后尽量不改 core |
| 调试台 | React 页面直接看事件流 |
| 可选鉴权 | Authentik OIDC / HS256 / 本地 stub |

产品参照仓是内部的 `RAG_Agent`（行为对齐、实现不照抄）。本仓是**绿场重写的模板**，方便开新业务时直接长出来。

---

## 适合 / 不适合

**适合**

- 要快速起一个「可流式对话的 Agent API」骨架
- 多个业务场景（域）共用同一套宿主与契约
- 团队希望分层清晰：core / 宿主 / domains

**不适合（或需二期）**

- 多副本 / K8s 多 Pod 抢同一 `thread_id`（需分布式锁）
- 开箱就要完整 OTel、硬中断工具副作用
- 把本仓当现成 SaaS，而不是模板

---

## 5 分钟跑起来

要求：Python 3.12+、Node 18+（调试台可选）。

```bash
# 1) 安装
pip install -e "packages/core[dev]" -e "apps/api[dev]"

# 2) 环境（内存 checkpointer，不必起 Postgres）
cp .env.example .env

# 3) 启动 API
cd apps/api
uvicorn main:app --reload --port 8000
```

另开终端启动调试台（推荐）：

```bash
cd apps/web
npm install
npm run dev
```

浏览器打开 **http://127.0.0.1:5173**

- route 选 `echo`：最小回声
- route 选 `demo_tools`：无 LLM，演示工具调用 + 扩展事件 `x.demo_tools.*`

Windows 也可在仓库根目录执行：`.\start-dev.ps1`（Linux/macOS：`./start-dev.sh`）。

健康检查：`GET http://127.0.0.1:8000/health` → `{"status":"ok"}`。

---

## 怎么用

### 1. 用调试台（最快）

1. 打开 http://127.0.0.1:5173  
2. 选 route，输入 query，点发送  
3. 下方时间线看 SSE 事件；`x.*` 默认折叠  
4. 需要时点 Cancel；「连点测 409」可验证同 thread 互斥  

### 2. 直接调 HTTP

**开流（SSE）**

```http
POST /chat/stream
Content-Type: application/json

{
  "query": "hello",
  "thread_id": "t-demo-001",
  "route": "echo"
}
```

成功：`200` + `Content-Type: text/event-stream`，每行大致为：

```text
data: {"type":"start","run_id":"r-...","sequence":1,...}

data: {"type":"text_delta","data":{"content":"hello"},...}

data: {"type":"done",...}
```

同 `thread_id` 已有运行中的 run → **409** `thread_busy`。  
未知 `route` → **400** `unknown_route`。

**取消**

```http
POST /chat/cancel
Content-Type: application/json

{ "thread_id": "t-demo-001" }
```

完整字段与事件样例见 [docs/contracts.md](docs/contracts.md)。

### 3. 加自己的业务（域）

新场景 = 新域插件，不要先改 `packages/core`。

1. 参照 `apps/api/domains/echo` 或 `demo_tools` 建 `apps/api/domains/<name>/`  
2. 实现 `state` / `tools` / `graph` / `bootstrap`  
3. 在 `apps/api/domains/bootstrap.py` 的 `register_all` 里注册  
4. 重启 API，`route="<name>"` 调用  

扩展事件：往图 State 的 `OUTBOUND_EXTENSIONS_KEY` 写 `[{type, data}]`，type 形如 `x.my_domain.done`。  
步骤与「什么时候才改 core」见 [docs/add-a-domain.md](docs/add-a-domain.md)。

### 4. 常用配置

| 变量 | 含义 |
|------|------|
| `USE_MEMORY_CHECKPOINTER=true` | 本地默认，不用 Postgres |
| `PG_DSN` / `PG_*` | 持久化 checkpointer（见 deploy） |
| `AUTH_REQUIRED` | 是否校验 Bearer |
| `HOOKS_BACKEND=noop\|logging` | 运行结束钩子 |

更多见 [docs/deploy.md](docs/deploy.md) 与 `.env.example`。

---

## 仓库结构（你需要摸的部分）

```text
packages/core/     # 编排内核：lifecycle、SSE 协议、LangGraph 防腐
apps/api/          # FastAPI 宿主；业务在 domains/*
  domains/echo/
  domains/demo_tools/
apps/web/          # React 调试台
docs/              # 契约、加域、部署、架构
```

依赖规矩：业务域不持有推流出口；编号与信封只在 lifecycle；详情见 [docs/architecture.md](docs/architecture.md)。

---

## 文档地图

| 文档 | 什么时候看 |
|------|------------|
| [contracts.md](docs/contracts.md) | 对接前端 / 写客户端 |
| [add-a-domain.md](docs/add-a-domain.md) | 加业务 |
| [deploy.md](docs/deploy.md) | Postgres、鉴权、多副本警告 |
| [architecture.md](docs/architecture.md) | 分层与组装根 |
| [硬化规格](docs/superpowers/specs/2026-07-24-template-hardening-optimization-design.md) | 一期能力边界与二期清单 |

---

## 开发与验证

```bash
python -m pytest packages/core/tests -v
cd apps/api && python -m pytest tests -v
python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
python scripts/import_scan_core.py
```

API 已启动时可用：`.\scripts\smoke_echo.ps1` 或 `./scripts/smoke_echo.sh`。

---

## 现状

- ✅ 一期模板硬化：契约单源、Fragment、工具 SSE、`demo_tools`、组装根瘦身  
- ⏳ 二期（按需）：Redis 锁 / 跨进程 cancel、`/ready`、JWKS TTL 等  

欢迎当模板 fork；若你在多副本环境直接水平扩展，请先读 deploy 里的锁说明，避免「模板能跑」被误当成「生产可扩」。
