# HTTP 接口参考

> 流式事件格式：[contracts.md](./contracts.md)。  
> 产品约定：[00-AgentBridge完整方案.md](./00-AgentBridge完整方案.md)。  
> 能力进度：[roadmap.md](./roadmap.md)（单机主承诺 = M0–M4）。

## 接口列表

| 方法 | 路径 | 说明 | 能力阶段 |
|------|------|------|----------|
| GET | `/health` | 活着没有 | M0 |
| POST | `/chat/stream` | 流式对话（SSE） | M0 |
| POST | `/chat/cancel` | 取消进行中的运行 | M0 |
| GET | `/ready` | 依赖是否就绪 | M4 |
| GET | `/threads` | 会话列表 | M2b |
| GET | `/threads/{id}/messages` | 消息历史 | M2b |
| GET | `/runs/{id}` | 某次运行状态（含等待审批） | M2b |
| GET | `/runs` | Run 列表 | **未实现**（用 `GET /admin/runs`） |
| GET | `/runs/{id}/events` | 已写入的事件（可回放） | M2b |
| GET | `/metrics` | Prometheus 指标 | M4 |
| GET/POST | `/approvals/*` | 人工审批（需要审批权限） | M6 |
| POST | `/ingest` | 文档写入知识库（需 `knowledge:write`；后端不支持时 501） | **已有**（阶段标签曾写 M7） |
| GET/POST | `/admin/*` | 管理：业务列表/配置等 | M8 |
| GET/POST | `/prompts/*` | Prompt 相关 | M5–M8 |

登录分层见完整方案「管理与鉴权」相关章节。

## 认证

```http
Authorization: Bearer <jwt_token>
```

## 错误长什么样

**HTTP**：`{"detail":{"code":"thread_busy","message":"..."}}`  
**SSE 事件**：`{"type":"error","run_id":"r-xxx","data":{"message":"...","code":"run_failed"}}`
