# 多机部署（M9）

> 仅在 **Plan5 / M9** 完成后，才可称「多机生产」。  
> 锁键为 `ab:lock:{storage_key}`，其中 `storage_key = {tenant_id}::{thread_id}`（**不要**再套一层 tenant 前缀）。  
> 默认锁 TTL 300s；长跑需加大或续租，否则锁过期后另一实例可能抢入。

## Compose：两 API + 一 Redis

```bash
docker compose up -d redis postgres
```

终端 A / B（不同端口）：

```bash
# 共用 Redis 锁与限流
export LOCK_BACKEND=redis
export RATE_LIMIT_BACKEND=redis
export REDIS_URL=redis://127.0.0.1:6379/0
export RATE_LIMIT_PER_MINUTE=120
export USE_MEMORY_CHECKPOINTER=false   # 生产建议 PG checkpointer
export PG_DSN=postgresql://postgres:change-me@127.0.0.1:5432/agent_base

pip install -e "apps/api[redis,datasource]"
cd apps/api
# 实例 A
uvicorn main:app --port 8001
# 实例 B
uvicorn main:app --port 8002
```

## 验证互斥

对同一 `thread_id` 同时向 8001 / 8002 发 `/chat/stream`：一侧应 `409 thread_busy`。

## 验证限流

将 `RATE_LIMIT_PER_MINUTE=2`，连打 3 次同一客户端 IP：第三次 `429 rate_limited`。

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `LOCK_BACKEND` | `memory` | `memory` \| `redis` |
| `RATE_LIMIT_BACKEND` | `memory` | `memory` \| `redis` |
| `REDIS_URL` | `redis://localhost:6379/0` | |
