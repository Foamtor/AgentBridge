# AgentBridge

> 自托管 Agent 接入底座。Python 包：`agentbridge-core`（import `agentbridge_core`）、`agentbridge-api`。

**这是什么：**  
一个可以自己部署的 **Agent 接入平台**。业务团队主要写「对话怎么走、调用哪些工具」；流式输出、互斥、取消、登录校验、权限、审计这些公共能力由平台统一提供。

**技术组合：** LangGraph（编排对话流程）+ FastAPI（HTTP 服务）+ SSE（一边生成一边往客户端推事件）。

---

## 先搞懂几个词（别被英文文件夹吓到）

| 你在文档里看到的 | 实际意思 |
|------------------|----------|
| **业务插件**（代码目录常叫 `domains/`） | 一块独立业务能力，比如「回声」「工具演示」「知识库问答」。像游戏卡带，插到同一台主机上用。 |
| **route** | 请求里写的名字，告诉服务「这次用哪个业务插件」。 |
| **SSE** | 服务器持续推送消息的方式，用来做流式对话。 |
| **接口约定（Port）** | 平台规定「检索/数据库要长什么样」；具体用 Postgres 还是别的，用适配器接上即可。 |

下面尽量用大白话；不再使用「金标域」「门禁」「运行面」这类内部说法。

---

## 它解决什么问题

做 Agent / 工具调用 / 知识库问答时，常见痛点是：

- 每次重写流式输出、同一会话互斥、取消、登录
- 业务流程和平台代码搅在一起
- 权限、落库、可观测各搞一套，很难回放和审计

本仓库约定：

| 你得到的 | 说明 |
|----------|------|
| 稳定的事件格式 | 固定几类事件 + 业务自定义的 `x.业务名.*` |
| 业务插件目录 | `apps/api/domains/<名字>`，尽量不改核心库 |
| 调试台 | React 页面看事件流 |
| 可选登录 | OIDC / JWT / 本地开发 stub |

---

## 适合 / 不适合

**适合**

- 自托管 Agent API，多个业务共用同一套接口
- 希望平台和业务分开：核心库 / 宿主服务 / 业务插件
- 想按能力逐步打开：权限、查库、审批、知识库、多 Agent

**不适合**

- 替代 LangGraph 官方云托管或 Studio 产品
- 研究型「任意 Agent 群聊」框架
- 当成企业账号中心（IAM）来用
- 默认就当「多台机器随便扩」——多机要按文档显式打开 Redis

---

## 你能做到哪一步

| 级别 | 你能做到什么 |
|------|----------------|
| **入门** | 起服务 → 选一个示例插件 → 流式对话 |
| **带权限** | JWT 角色 → 工具该不该出现、该不该执行 → 能查历史消息；（可选）查业务库 |
| **单机可运维** | 健康检查、限流、指标、审计记录、部署清单 |
| **进阶** | 人工审批、知识库引用、多 Agent、TypeScript 客户端 |

**对外主承诺：** 单机生产可用。多机要额外配置，见 [multi-instance.md](docs/multi-instance.md)。

---

## 5 分钟跑起来

需要：Python 3.12+、Node 18+（调试台可选）。

```bash
pip install -e "packages/core[dev]" -e "apps/api[dev]"
cp .env.example .env
cd apps/api
uvicorn main:app --reload --port 8000
```

调试台：

```bash
cd apps/web
npm install
npm run dev
```

打开 **http://127.0.0.1:5173**，选 `echo` 或 `demo_tools` 试对话。

也可在仓库根目录运行：`.\start-dev.ps1` / `./start-dev.sh`。  
健康检查：`GET http://127.0.0.1:8000/health`。

---

## 怎么用

### 1. 调试台

选业务插件（route）→ 发送 → 看事件时间线；可测取消、同一会话冲突（HTTP 409）。

### 2. 直接调 HTTP

```http
POST /chat/stream
Content-Type: application/json

{"query":"hello","thread_id":"t-demo-001","route":"echo"}
```

取消：`POST /chat/cancel`。  
事件格式：[docs/contracts.md](docs/contracts.md)；接口列表：[docs/api-reference.md](docs/api-reference.md)。

### 3. 加自己的业务

复制 `echo` / `demo_tools` 或 `_scaffold`，改图和工具，在 `domains/bootstrap.py` 注册。  
说明：[docs/add-a-domain.md](docs/add-a-domain.md)（标题是「怎么加业务插件」）。

### 4. 常用配置

| 变量 | 含义 |
|------|------|
| `USE_MEMORY_CHECKPOINTER=true` | 本地默认，状态放内存 |
| `PG_DSN` / `PG_*` | Postgres（持久化对话检查点） |
| `AUTH_REQUIRED` | 是否校验 Bearer Token |
| `HOOKS_BACKEND=noop\|logging` | 运行钩子 |

详见 [docs/deploy.md](docs/deploy.md)、`.env.example`。

---

## 仓库结构

```text
packages/core/     # 编排核心库
apps/api/domains/  # 业务插件（一个文件夹 = 一个 route）
apps/web/          # 调试台
docs/              # 说明文档与路线图
```

---

## 文档地图

| 文档 | 用途 |
|------|------|
| [00-AgentBridge完整方案.md](docs/00-AgentBridge完整方案.md) | 产品总说明（正式约定以这里为准） |
| [roadmap.md](docs/roadmap.md) | 能力做到哪一步了 |
| [contracts.md](docs/contracts.md) | 对话事件格式 |
| [api-reference.md](docs/api-reference.md) | HTTP 接口列表 |
| [architecture.md](docs/architecture.md) | 代码怎么分层 |
| [deploy.md](docs/deploy.md) | 怎么部署（单机 / 多机） |
| [database-integration.md](docs/database-integration.md) | 业务库 vs 对话检查点 |
| [add-a-domain.md](docs/add-a-domain.md) | 怎么加业务插件 |
| [multi-instance.md](docs/multi-instance.md) | 多机部署 |
| `docs/superpowers/` | 历史设计与实施记录；和总说明冲突时，以总说明为准 |

---

## 开发与验证

```bash
python -m pytest packages/core/tests -v
cd apps/api && python -m pytest tests -v
# 也可以在仓库根目录一次跑两边：
python -m pytest packages/core/tests apps/api/tests -q
python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
python scripts/import_scan_core.py
python scripts/run_evals.py
```

冒烟：`.\scripts\smoke_echo.ps1` / `./scripts/smoke_echo.sh`。

---

## 现状与下一步

| | |
|--|--|
| ✅ 现在 | 入门到进阶主路径已合入本仓库默认分支：流式对话、权限、单机运维、审批、知识库示例、多 Agent、SDK、可选 Redis 多机 |
| ⏭ 建议 | 接真实业务插件；按单机/多机把配置跑实 |
| ❌ 不做 | 云 Studio、研究型任意群聊、替代企业账号中心 |

完整约定见 [完整方案](docs/00-AgentBridge完整方案.md) 与 [路线图](docs/roadmap.md)。
