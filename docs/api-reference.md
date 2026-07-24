# HTTP API 参考

> SSE 契约真源：[contracts.md](./contracts.md)。  
> 产品真源：[00-AgentBridge完整方案.md](./00-AgentBridge完整方案.md) **v4.1**。  
> 里程碑：[roadmap.md](./roadmap.md)（**v1.0 = M0–M4**）。

## 端点总表

| 方法 | 路径 | 说明 | 里程碑 |
|------|------|------|--------|
| GET | `/health` | 健康检查 | M0 |
| POST | `/chat/stream` | SSE | M0 |
| POST | `/chat/cancel` | 取消 | M0 |
| GET | `/ready` | 依赖就绪 | M4 |
| GET | `/threads` | 对话列表 | M2b |
| GET | `/threads/{id}/messages` | 消息投影 | M2b |
| GET | `/runs`、`/runs/{id}` | Run 状态（含 `awaiting_approval`） | M2b |
| GET | `/runs/{id}/events` | EventLog | M2b |
| GET | `/metrics` | Prometheus | M4 |
| GET/POST | `/approvals/*` | 审批（需 approval 权限） | M6 |
| POST | `/ingest` | 摄取（需 admin 写权限） | M7 |
| GET/POST | `/admin/*` | 域/配置/策略 | M8 |
| GET/POST | `/prompts/*` | Prompt | M5–M8 |

鉴权分层见完整方案 §4.7。

## 认证

```http
Authorization: Bearer <jwt_token>
```

## 错误形状

**HTTP**：`{"detail":{"code":"thread_busy","message":"..."}}`  
**SSE**：`{"type":"error","run_id":"r-xxx","data":{"message":"...","code":"run_failed"}}`
