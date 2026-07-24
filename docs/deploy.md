# 部署说明

> 对齐 [00-AgentBridge完整方案.md](./00-AgentBridge完整方案.md)。  
> **单机主承诺 = M0–M4**。多机见 [multi-instance.md](./multi-instance.md)（对应能力 M9）。

## 怎么选部署方式

| 模式 | 会话锁 | 限流 | 事件存储 | 说明 |
|------|--------|------|----------|------|
| 本地开发 | 本进程内存 | 可选 | 内存或 Postgres | 默认 |
| 单机生产 | 本进程内存 | 本进程或 Redis | Postgres | 主承诺 |
| 多机 | Redis（或数据库锁） | Redis | 集中式 Postgres | 需显式配置 |

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
