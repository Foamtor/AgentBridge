# Agent-Base

> 产品方向名：**AgentBridge**（见 [完整方案 v4.1.1](docs/00-AgentBridge完整方案.md)）。当前仓库/包名仍为 Agent-Base，品牌重命名与能力里程碑正交。

**用 LangGraph 做 AI 业务时，可直接 fork 的自托管 Agent 接入平台。**

把流式对话、取消、线程锁、SSE 契约、域插件一次搭好；演进方向是以 **Run/Event 为真源**，统一 **策略引擎** 与 **模型出口（Gateway）**，再按需打开记忆、RAG、审批、多 Agent 与 SDK。

> **当前现状（≈ v1.0 单机）**：M0–M4 已齐（安全接入、查库、ready/metrics/限流/InputValidator/OTel noop）。默认进程内锁与限流。  
> **能力愿景**：见 [roadmap.md](docs/roadmap.md)（M0–M10，不计人天）。  
> **主承诺口径**：**v1.0 = 单机生产**（非多机）；多机见里程碑 M9。

---

## 它解决什么问题

做 Agent / 工具调用 / RAG 类产品时，常见痛点是：

- 每次重写 SSE、互斥、取消、鉴权
- 业务图和宿主搅在一起
- 权限、落库、可观测各搞一套，难以回放与审计

本仓提供统一运行面与域插件模型：

| 你得到的（已有） | 说明 |
|------------------|------|
| 稳定 SSE 契约 | 九类事件 + `x.<domain>.*` |
| 域插件 | `apps/api/domains/<name>`，尽量不改 core |
| 调试台 | React 看事件流 |
| 可选鉴权 | OIDC / HS256 / 本地 stub |

| 规划中（v4.1） | 说明 |
|----------------|------|
| EventLog + 回放 | **已提交**事件为真源；append 后于 SSE |
| PolicyEngine | 按 action：list_tools / invoke_tool / read_data / emit_text |
| LLM Gateway | 路由、降级、PII；`direct\|gateway` 过渡 |
| 知识 / 治理 / 协作 | Memory、RAG、审批（等待时释锁）、多 Agent、SDK |

---

## 适合 / 不适合

**适合**

- 自托管 Agent API 底座，多业务域共享契约
- 要分层清晰：core / 宿主 / domains
- 希望按里程碑加权限、RAG、审批、多 Agent，而不是一次性绑死巨型框架

**不适合 / 非目标**

- 替代 LangGraph 云托管 / 官方 Studio
- 研究型任意 GroupChat
- 未完成 M9 前把多副本当开箱能力

---

## 接入体验分级

| 级别 | 你能做到什么 | 里程碑 |
|------|----------------|--------|
| **L1** | 起服务 + 域 + SSE 对话 | M0–M1 |
| **L2** | JWT 角色 + tool 策略 + 消息可查 +（可选）查库 | M2a–M3 |
| **L3** | 审计（M2）+ 单机限流 / metrics / OTel / 部署清单 | M2 + M4 |
| **进阶** | 审批写入、RAG、多 Agent、SDK | M6–M8 |
| **v1.0** | **M0–M4 全部通过**（单机）；不强制 M5+ | 见路线图 |

---

## 5 分钟跑起来（L1）

要求：Python 3.12+、Node 18+（调试台可选）。

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

打开 **http://127.0.0.1:5173** — `echo` / `demo_tools`。

或仓库根目录：`.\start-dev.ps1` / `./start-dev.sh`。  
健康检查：`GET http://127.0.0.1:8000/health`。

---

## 怎么用

### 1. 调试台

选 route → 发送 → 看 SSE 时间线；Cancel / 连点测 409。

### 2. HTTP

```http
POST /chat/stream
Content-Type: application/json

{"query":"hello","thread_id":"t-demo-001","route":"echo"}
```

取消：`POST /chat/cancel`。契约见 [docs/contracts.md](docs/contracts.md)；端点总表见 [docs/api-reference.md](docs/api-reference.md)。

### 3. 加域

参照 `echo` / `demo_tools` → `domains/bootstrap.py` 注册。见 [docs/add-a-domain.md](docs/add-a-domain.md)。

### 4. 常用配置

| 变量 | 含义 |
|------|------|
| `USE_MEMORY_CHECKPOINTER=true` | 本地默认 |
| `PG_DSN` / `PG_*` | Postgres checkpointer |
| `AUTH_REQUIRED` | Bearer 校验 |
| `HOOKS_BACKEND=noop\|logging` | 运行钩子 |

见 [docs/deploy.md](docs/deploy.md)、`.env.example`。

---

## 仓库结构

```text
packages/core/     # 编排内核
apps/api/domains/  # 业务域
apps/web/          # 调试台
docs/              # 完整方案 v4、路线图、契约、架构
```

---

## 文档地图

| 文档 | 用途 |
|------|------|
| [00-AgentBridge完整方案.md](docs/00-AgentBridge完整方案.md) | **产品真源 v4.1** |
| [roadmap.md](docs/roadmap.md) | M0–M10；v1.0=M0–M4；[Plan 索引](docs/superpowers/plans/README.md) · [依赖](docs/superpowers/plans/DEPENDENCIES.md) |
| [contracts.md](docs/contracts.md) | SSE / chat 契约 |
| [api-reference.md](docs/api-reference.md) | HTTP 端点总表 |
| [architecture.md](docs/architecture.md) | 当前结构 + 目标架构 |
| [deploy.md](docs/deploy.md) | 部署与单机/多机矩阵 |
| [database-integration.md](docs/database-integration.md) | DataSource vs checkpointer |
| [add-a-domain.md](docs/add-a-domain.md) | 加域 |
| `docs/superpowers/` | 历史规格；与 v4.1 冲突时以 v4.1 为准 |

---

## 开发与验证

```bash
python -m pytest packages/core/tests -v
cd apps/api && python -m pytest tests -v
python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
python scripts/import_scan_core.py
```

Smoke：`.\scripts\smoke_echo.ps1` / `./scripts/smoke_echo.sh`。

---

## 现状与下一步

| | |
|--|--|
| ✅ 现在 | **v1.0 单机门禁**：M0–M4（含 `/ready` `/metrics` 限流 InputValidator） |
| ⏭ 建议下一切片 | **Plan4**（Gateway / Context / Filter / Approval，M5–M7） |
| ⏳ 愿景 | M5–M10；多机仍是 **M9**，不在 v1.0 范围 |

完整定义见 [完整方案 v4.1](docs/00-AgentBridge完整方案.md) 与 [路线图](docs/roadmap.md)。
