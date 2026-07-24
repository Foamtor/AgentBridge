# Deploy

> 对齐 [00-AgentBridge完整方案.md](./00-AgentBridge完整方案.md) v4.1 **§9**。  
> **v1.0 = M0–M4**（单机）。多机见 **M9**。

## 部署矩阵

| 模式 | 锁 | 限流 | 事件存储 | 说明 |
|------|----|------|----------|------|
| 本地 | 进程内 | 可选 | 内存或 PG | 默认开发 |
| 单机生产 | 进程内 | 进程内或 Redis | Postgres | 主承诺 |
| 多机 | Redis/DB | Redis | 集中 Postgres | M9 |

## Local (memory checkpointer)

```bash
pip install -e "packages/core[dev]" -e "apps/api[dev]"
cp .env.example .env
# USE_MEMORY_CHECKPOINTER=true
cd apps/api && uvicorn main:app --reload --port 8000
```

Web: `cd apps/web && npm install && npm run dev`  
或根目录：`./start-dev.sh` / `.\start-dev.ps1`。

## Postgres checkpointer

```bash
docker compose up -d postgres
# USE_MEMORY_CHECKPOINTER=false
# PG_DSN=postgresql://user:pass@host:5432/db
pip install -e "packages/core[postgres]"
```

`HOOKS_BACKEND=noop|logging` 切换运行钩子。

## Authentik（可选）

见 `infra/authentik/README.md`。`AUTH_REQUIRED=true` 时配置 `OIDC_ISSUER` 或 `OIDC_JWT_SECRET`；本地可用 `AUTH_DEV_STUB=1`（**禁止生产**）。

### JWT → RunContext（M2a+）

| claim | 字段 |
|-------|------|
| `sub` | `user_id` |
| `tenant_id` / `tid` | `tenant_id` |
| `roles` | `roles` |
| `permissions` / `perms` | `permissions` |

两阶段注入与 checkpointer 键 `{tenant_id}::{thread_id}` 见完整方案 §4.1。  
`AUTH_REQUIRED=false` 时开发默认 admin。

## 单机上线检查清单（L3 = M2 审计 + M4）

- [ ] 需要会话持久化时关闭 memory checkpointer，Postgres 可达
- [ ] `AUTH_REQUIRED=true`，关闭 `AUTH_DEV_STUB`
- [ ] 确认单实例，或已接受无分布式锁风险
- [ ] `/health`、`/ready`、`/metrics` 已验证；`RATE_LIMIT_PER_MINUTE>0` 时限流返回 `code=rate_limited`
- [ ] 超长 query 返回 `400 invalid_input`（InputValidator）
- [ ] `OTEL_ENABLED` 可选（当前为 noop span，开启不抛错）
- [ ] 审计可用（M2a）；EventLog/消息可查（M2b）
- [ ] `ENABLE_DATA_SOURCE` 与 checkpointer 开关独立；开启时 `/ready` 会 `SELECT 1`
- [ ] 日志不落用户原文 / LLM 全文
- [ ] 管理面/审批 API 权限已按 §4.7 配置（若已交付）

## M4 环境变量（单机生产面）

| 变量 | 默认 | 说明 |
|------|------|------|
| `RATE_LIMIT_PER_MINUTE` | `0`（关闭） | 进程内滑动窗口；按客户端 IP |
| `OTEL_ENABLED` | `false` | 开启后仍为 noop span（可扩展） |
| `ENABLE_DATA_SOURCE` | `false` | 与 `USE_MEMORY_CHECKPOINTER` 独立 |

运维探针：`GET /health`（存活）、`GET /ready`（依赖；未启用的项 **skipped**）、`GET /metrics`（Prometheus 文本）。
