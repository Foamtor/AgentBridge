# 数据库接入

> 对齐完整方案 **v4.1.1** 产品线 C / 里程碑 **M3**。  
> **DataSource Port** 见 Plan2；与 Postgres **checkpointer** 职责分离。  
> **`ENABLE_DATA_SOURCE` 独立于 `USE_MEMORY_CHECKPOINTER`**（可同时 memory 会话 + 业务 PG，或同实例不同库）。

## 两件事

| 能力 | 用途 | 状态 |
|------|------|------|
| Checkpointer（`PG_DSN`） | LangGraph 会话状态 | 已有 |
| DataSource | 业务 tool 查业务表 | 规划 M3 |
| EventLog / Message 投影 | run 事件与对话查询 | 规划 M2b（可与 checkpointer 同实例分表） |

## 目标 API（M3）

```python
class DataSource(Protocol):
    async def query(self, sql: str, *params) -> list[dict]: ...
    async def execute(self, sql: str, *params) -> int: ...
    async def close(self) -> None: ...
```

- 一等支持 Postgres；MySQL/Mongo 为扩展 adapter
- 仅在组装根构造；经 RunContext / 元数据交给 tool
- tool 内 `get_run_context(config)`；禁止默认参数注入

## 权限与过滤

- tool 声明 `required_permissions` / `required_roles`（M2a Policy：`list_tools` + `invoke_tool`）
- DataFilter（M6）：字段白名单 + 参数化；**无规则 = 无数据**

## 现在

域内可先用自有 DB 客户端；Port 落地后再迁，便于 fake 测试。
