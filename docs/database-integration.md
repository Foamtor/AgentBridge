# 数据库接入

> 对应完整方案里「查业务库」能力（M3）。  
> **业务库访问** 和 **对话会话检查点（checkpointer）** 是两件事，开关也分开。  
> `ENABLE_DATA_SOURCE` **不依赖** `USE_MEMORY_CHECKPOINTER`（可以一边内存会话、一边连业务 Postgres）。

## 两件事别混

| 能力 | 用途 | 状态 |
|------|------|------|
| Checkpointer（`PG_DSN`） | LangGraph 会话状态 | 已有 |
| DataSource（业务库接口） | 工具去查业务表 | 已有 |
| 事件日志 / 消息查询 | 回放与对话历史 | 已有（可与 checkpointer 同库不同表） |

## 业务库接口长什么样

```python
class DataSource(Protocol):
    async def query(self, sql: str, *params) -> list[dict]: ...
    async def execute(self, sql: str, *params) -> int: ...
    async def close(self) -> None: ...
```

- 优先支持 Postgres；MySQL/Mongo 可作为扩展适配器  
- 只在服务启动时创建；经请求上下文交给工具  
- 工具里用 `get_run_context(config)` 取上下文；不要用「默认参数偷偷注入」

## 权限与过滤

- 工具声明需要的角色/权限；列工具和执行工具都会检查  
- 数据过滤（偏治理能力）：字段白名单 + 参数化查询；**没有规则就不要返回数据**

## 现在怎么开

- 默认：`ENABLE_DATA_SOURCE=false` → 空实现（什么也不查）  
- 开启：`ENABLE_DATA_SOURCE=true`，DSN 用 `DATA_SOURCE_DSN`，或回退到 `PG_DSN` / 分量配置  
- 官方示例插件：`demo_readonly`（`list_orders`，需要 `order:read`）；表结构见 `apps/api/migrations/002_demo_readonly.sql`  
- 可选依赖：`pip install -e "apps/api[datasource]"`（asyncpg）

业务插件里仍可先用自有数据库客户端；新插件建议走 `ctx.metadata["data_source"]` + `get_run_context(config)`。
