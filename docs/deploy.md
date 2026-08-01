# 部署说明

> 对齐 [00-AgentBridge完整方案.md](./00-AgentBridge完整方案.md)。  
> **单机主承诺 = M0–M4**。多机见 [multi-instance.md](./multi-instance.md)（对应能力 M9）。

## 怎么选部署方式

| 模式 | 会话锁 | 限流 | 事件存储 | 说明 |
|------|--------|------|----------|------|
| 本地开发 | 本进程内存 | 可选 | 内存或 Postgres | 默认 |
| 单机生产 | 本进程内存 | 本进程或 Redis | Postgres | 主承诺 |
| 多机 | Redis（或数据库锁） | Redis | 集中式 Postgres | 需显式配置 |

## 支持矩阵与当前承诺

| 环境 | PostgreSQL / pgvector | Redis | OIDC | LLM Gateway | RAG 后端 | 当前承诺 |
|------|------------------------|-------|------|-------------|----------|----------|
| 本地体验 | 可不用 | 不用 | 可不用 | 可用默认 Fake 模型 | `fake` | 仅开发与 CI |
| 单机技术预览 | 推荐 Postgres | 可不用 | 可选 | direct 或 gateway | `fake`、`langchain_pg`、`external` | 可体验，不承诺生产稳定 |
| 单机生产验收候选 | 必须真实 Postgres；RAG 另需 pgvector | 进程内或 Redis | 必须启用 | 必须配置真实出口 | 按下方支持矩阵 | 仍须完成 P1/P2/P3 发布门槛 |
| 双实例验证 | 集中式 Postgres | 必须 Redis 锁与限流 | 必须启用 | 必须配置真实出口 | 按下方支持矩阵 | P2 验收项，尚非默认承诺 |

- `fake` 仅本地/CI，不能作为生产证据。
- `langchain_pg` 需要 pgvector、`[rag]` extra 和兼容 embedding 服务。
- `external` 支持检索；不支持摄取时 `POST /ingest` 返回 501。
- 多实例必须设置 Redis 锁和限流；未演练前仅技术预览。

## 两档 Quick Start

| 档 | 适用 | 数据库 | 时间 |
|----|------|--------|------|
| **Fake**（零依赖） | 快速体验对话 / 工具 | 无（内存） | ~5 min |
| **完整 RAG** | 知识问答 + 入库 | PG + pgvector | ~30 min |

Fake 档：直接装 pip + 启动 uvicorn。  
完整 RAG 档：`docker compose --profile rag up -d` 起 pgvector 实例，再装 `[rag]` extra，配置 `KNOWLEDGE_BACKEND=langchain_pg`，跑迁移脚本。  
详见 README Quick Start。

---

## 本地（内存会话）

```bash
pip install -e "packages/core[dev]" -e "apps/api[dev]"
cp .env.example .env
# USE_MEMORY_CHECKPOINTER=true
cd apps/api && uvicorn main:app --reload --port 8000
```

调试台：`cd apps/web && npm install && npm run dev`  
或仓库根目录：`./start-dev.sh` / `.\start-dev.ps1`。

## Postgres 会话检查点

```bash
docker compose up -d postgres
# USE_MEMORY_CHECKPOINTER=false
# PG_DSN=postgresql://user:pass@host:5432/db
pip install -e "packages/core[postgres]"
```

`HOOKS_BACKEND=noop|logging` 切换运行钩子。

## Authentik（可选登录）

见 `infra/authentik/README.md`。  
`AUTH_REQUIRED=true` 时配置 `OIDC_ISSUER` 或 `OIDC_JWT_SECRET`。  
本地可用 `AUTH_DEV_STUB=1`（**禁止用于生产**）。

### JWT 里有哪些字段会进请求上下文

| JWT 字段 | 进上下文的字段 |
|----------|----------------|
| `sub` | `user_id` |
| `tenant_id` / `tid` | `tenant_id` |
| `roles` | `roles` |
| `permissions` / `perms` | `permissions` |

会话落库键为 `{tenant_id}::{thread_id}`。  
`AUTH_REQUIRED=false` 时，开发环境默认相当于管理员。

## 单机上线前检查

- [ ] 需要会话持久化时：关闭内存 checkpointer，确认 Postgres 可达  
- [ ] `AUTH_REQUIRED=true`，关闭 `AUTH_DEV_STUB`  
- [ ] 确认是单实例，或已接受「无分布式锁」的风险；多机请按多机文档配置  
- [ ] 验证 `/health`、`/ready`、`/metrics`；限流打开时超限返回 `code=rate_limited`  
- [ ] 过长输入返回 `400 invalid_input`  
- [ ] `OTEL_ENABLED` 可选（当前为占位实现，开启不应直接报错）  
- [ ] 审计可用；事件与消息可查  
- [ ] `ENABLE_DATA_SOURCE` 与 checkpointer 开关互不影响；开启业务库时 `/ready` 会做连通性检查  
- [ ] 日志不要落用户原文 / 模型全文  
- [ ] 管理接口、审批接口的权限已按方案配置（若你启用了这些接口）

## 单机相关环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `RATE_LIMIT_PER_MINUTE` | `0`（关闭） | 按客户端 IP 计数 |
| `OTEL_ENABLED` | `false` | 开启后仍为占位 span（可扩展） |
| `ENABLE_DATA_SOURCE` | `false` | 与 `USE_MEMORY_CHECKPOINTER` 独立 |

探针：`GET /health`（活着）、`GET /ready`（依赖；未启用的项标成 skipped）、`GET /metrics`（Prometheus 文本）。

## 知识后端（R-A · M11）

> 设计：[platform-ra-design](./superpowers/specs/2026-07-27-platform-ra-design.md)；计划：[platform-ra](./superpowers/plans/2026-07-27-platform-ra.md)。  
> **默认仍是 Fake**；下列变量在 `KNOWLEDGE_BACKEND=langchain_pg` 时生效。

| 变量 | 说明 |
|------|------|
| `KNOWLEDGE_BACKEND` | `fake`（默认）\| `langchain_pg`（R-A）\| `external` / `product`（R-C） |
| `KB_DSN` | 知识库 PG（可省略则用 `PG_DSN`）；需 pgvector |
| `EMBED_API_BASE` / `EMBED_MODEL` / `EMBED_API_KEY` | Embedding（OpenAI 兼容；本机 TEI） |
| `EMBED_DIMENSIONS` | 向量维数，须与 embedding 模型输出一致 |

> 同一知识集合不能混用不同向量维度。P2-A 参考配置为 `BAAI/bge-m3` / `512`；已有集合切换模型时必须重建并重嵌入，升级流程留在 P2-B。
| `KB_EXTERNAL_BASE_URL` | 仅 `external`（R-C） |

安装：`pip install -e "apps/api[rag]"`。  
Postgres：`docker compose --profile rag up -d`（`pgvector/pgvector:pg16`）。  
使用说明：[knowledge-base.md](./knowledge-base.md)。
