# 多机部署

> 只有按下面方式配好共享锁/限流之后，才适合叫「多机生产」。  
> 锁的键是 `ab:lock:{storage_key}`，其中 `storage_key = {租户}::{会话 id}`（**不要**再套一层租户前缀）。  
> 默认锁过期时间 300 秒；特别长的任务要加大过期时间或做续租，否则锁过期后另一台机器可能抢入。

## 两台 API + 一台 Redis（示意）

```bash
docker compose up -d redis postgres
```

两个终端（不同端口）：

```bash
export LOCK_BACKEND=redis
export RATE_LIMIT_BACKEND=redis
export REDIS_URL=redis://127.0.0.1:6379/0
export RATE_LIMIT_PER_MINUTE=120
export USE_MEMORY_CHECKPOINTER=false   # 生产建议用 Postgres 会话
export PG_DSN=postgresql://postgres:change-me@127.0.0.1:5432/agentbridge

pip install -e "apps/api[redis,datasource]"
cd apps/api
# 实例 A
uvicorn main:app --port 8001
# 实例 B
uvicorn main:app --port 8002
```

## 怎么验证「同一会话不会双开」

自动化：`apps/api/tests/test_redis_lock.py` 用内存假 Redis，模拟两个进程抢同一把锁。

手工：对同一个 `thread_id` 同时向 8001 / 8002 发 `/chat/stream`，其中一侧应返回 `409 thread_busy`。

## 怎么验证限流

把 `RATE_LIMIT_PER_MINUTE=2`，同一客户端 IP 连打 3 次：第三次应 `429 rate_limited`。

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `LOCK_BACKEND` | `memory` | `memory` 或 `redis` |
| `RATE_LIMIT_BACKEND` | `memory` | `memory` 或 `redis` |
| `REDIS_URL` | `redis://localhost:6379/0` | |
