# 部署说明

> 对齐 [00-AgentBridge完整方案.md](./00-AgentBridge完整方案.md)。  
> **单机主承诺 = M0–M4**。多机见 [multi-instance.md](./multi-instance.md)（对应能力 M9）。

## 怎么选部署方式

| 模式 | 会话锁 | 限流 | 事件存储 | 说明 |
|------|--------|------|----------|------|
| 本地开发 | 本进程内存 | 可选 | Postgres（Compose 默认） | 默认 |
| 单机生产 | 本进程内存 | 本进程或 Redis | Postgres | 主承诺 |
| 多机 | Redis（或数据库锁） | Redis | 集中式 Postgres | 需显式配置 |

## 支持矩阵与当前承诺

| 环境 | PostgreSQL / pgvector | Redis | OIDC | LLM Gateway | RAG 后端 | 当前承诺 |
|------|------------------------|-------|------|-------------|----------|----------|
| 本地体验 | 可不用 | 不用 | 可不用 | 可用默认 Fake 模型 | `fake` | 仅开发与 CI |
| 单机开发 | 推荐 Postgres | 可不用 | 可选 | direct 或 gateway | `fake`、`langchain_pg`、`external` | 开发与验证 |
| 单机生产 | 必须真实 Postgres；RAG 另需 pgvector | 进程内或 Redis | 必须启用 | 必须配置真实出口 | 按下方支持矩阵 | v1.0.0 主承诺 |
| 双实例验证 | 集中式 Postgres | 必须 Redis 锁与限流 | 必须启用 | 必须配置真实出口 | 按下方支持矩阵 | P2 验收项，尚非默认承诺 |

- `fake` 仅本地/CI，不能作为生产证据；`OBSERVABILITY_STORE_BACKEND=memory` 同样不能作为 P1/P2 验收证据。
- `langchain_pg` 需要 pgvector、`[rag]` extra 和兼容 embedding 服务。
- `external` 支持检索；不支持摄取时 `POST /ingest` 返回 501。
- 多实例必须设置 Redis 锁和限流；未演练前不属于默认 v1.0.0 承诺。

## 两档 Quick Start

| 档 | 适用 | 数据库 | 时间 |
|----|------|--------|------|
| **Fake**（零依赖） | 快速体验对话 / 工具 | 无（内存） | ~5 min |
| **完整 RAG** | 知识问答 + 入库 | PG + pgvector | ~30 min |

Fake 档：直接装 pip + 启动 uvicorn。  
完整 RAG 档：`docker compose --profile rag up -d` 起 pgvector 实例，再装 `[rag]` extra，配置 `KNOWLEDGE_BACKEND=langchain_pg`，跑迁移脚本。  
详见 README Quick Start。

## v1.0.0 Compose demo

在仓库根目录执行，并先确保根目录存在 `.env`（可执行 `copy .env.example .env`）。默认使用国内 DaoCloud 镜像代理拉取基础镜像；如网络环境可以直接访问 Docker Hub，可在 `.env` 中设置 `IMAGE_REGISTRY=docker.io`：

```bash
docker compose up --build
```

打开 `http://127.0.0.1:8080`。默认服务为 Web、API 和 pgvector PostgreSQL；Web 通过同源 `/api` 访问 API，PostgreSQL 不映射宿主机端口。默认使用离线 FakeChatModel、fake knowledge、脱敏工单数据和本地管理员登录，适合验证 `work_order_ops` 的查询、图表、草稿和审批。

首次启动时 API 会在容器日志中仅打印一次 `admin` 的一次性密码：`docker compose logs api`。登录后必须设置至少 8 位、同时包含字母和数字的密码才能访问工作台。密码只保存为 Argon2id 哈希，浏览器仅保存 HttpOnly 会话 Cookie。若丢失初始密码且尚未改密，可仅对演示环境执行 `docker compose down --volumes` 后重新启动；这会删除该 Compose 演示数据。

停止：`docker compose down`。如需**删除所有本地演示数据**再初始化，执行 `docker compose down --volumes`；这只应对本项目演示 volume 使用。Redis 与 Authentik 分别用 `--profile redis` 与 `--profile auth` 按需启动；Authentik 默认也走 DaoCloud 的 GHCR 代理，可通过 `AUTHENTIK_IMAGE` 覆盖。

### 真实模型案例验证

默认 `work_order_ops` 是离线 Fake 演示：它用脱敏的 Compose 数据和确定性模型桩，适合确认平台链路。要验证真实模型如何选择案例 tools、读取自己的工单数据或检索知识，设置下列变量后重启 API：

```dotenv
LLM_MODE=openai_compatible
LLM_API_BASE=https://your-openai-compatible-endpoint/v1
LLM_MODEL=your-model-name
LLM_API_KEY=replace-me
ENABLE_DATA_SOURCE=true
DATA_SOURCE_DSN=postgresql://user:password@host:5432/your_business_database
# 需要真实知识检索时，再选择 langchain_pg 或 external，而不是 fake。
KNOWLEDGE_BACKEND=external
KB_EXTERNAL_BASE_URL=https://your-rag-service
```

然后在验证工作台选择“真实模型”。该模式只把平台权限筛选后的 `work_order_ops` 读工具交给模型选择，工具仍以当前租户执行；创建写入仍经过草稿、人工审批和幂等动作。没有设置 `LLM_MODE=openai_compatible` 时，真实模型模式会明确返回 `real_model_not_configured`，不会悄悄回退到 Fake。

在 `/models` 管理页可由本地管理员再次确认密码后生成 Fernet 密钥，或粘贴已有密钥；Compose API 将根目录 `.env` 持久挂载到容器，服务端只更新该文件，不会返回或写入 PostgreSQL。保存后密钥会立即在当前 API 生效；重启 API 后仍会从挂载文件恢复。也可手动用 `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` 生成密钥。Key 会在模型 API Key 写入 PostgreSQL 前加密，读取接口和浏览器不会得到明文。必须将该加密密钥保存在数据库之外且持续保留；丢失密钥会导致已保存的模型凭据无法解密。

---

## 本地（隔离内存会话）

```bash
pip install -e "packages/core[dev]" -e "apps/api[dev]"
cp .env.example .env
# 仅限隔离测试或离线 Fake 演示；P1/P2 验收使用 false。
# USE_MEMORY_CHECKPOINTER=true
# OBSERVABILITY_STORE_BACKEND=memory
python -m uvicorn main:app --app-dir apps/api --reload --reload-dir apps/api --reload-dir packages/core/src --port 8000
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
验证工作台默认使用 `AUTH_MODE=local`：首次启动从 API 容器日志读取一次性管理员密码，登录后先设置强密码。仅测试 fixture 可使用 `AUTH_MODE=disabled`；生产环境禁止关闭认证。

## 单机上线前检查

- [ ] P1/P2 验收：关闭内存 checkpointer、使用 `OBSERVABILITY_STORE_BACKEND=postgres`，确认 Postgres 可达
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
