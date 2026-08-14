# 开发者控制台

← [第一个插件](./04-first-plugin.md) · [文档目录](../INDEX.md)

---

## 它是什么（先分清）

仓库里的 **`apps/web`** 是给**集成方 / 管理员**使用的开发者控制台，包含三类入口：

- 根页面 `/`：Verification Workbench，用 `work_order_ops` 验证查询、图表、知识检索和审批黄金链路
- `/playground`：插件调试台，用来编辑请求、选择 route、查看实时 SSE、工具轨迹和契约检查
- `/admin` 及相关页面：查看插件、运行、模型、Prompt、用量和知识后端状态

**不是**最终用户的业务 App。  
客户最终使用的业务页面仍应由你们自己的前端消费 AgentBridge 的 HTTP/SSE 接口。

> 若你按顺序读 guide：在 [快速开始](./02-quickstart.md) 里可能已经打开过它。  
> 这篇补的是：**边界**、菜单大概有什么、和 API 怎么配合——不是要求你现在才第一次启动。

## 怎么打开（复习）

1. API 先在 `8000` 跑着（见 [快速开始](./02-quickstart.md)）  
2. `cd apps/web && npm install && npm run dev`  
3. 浏览器打开 <http://127.0.0.1:5173>

默认 `AUTH_MODE=local` 时，先使用 API 启动日志中的一次性 `admin` 密码登录并完成强制改密。首次验证建议在根页面运行 `work_order_ops`；开发插件时进入 `/playground?route=<名字>`。最小链路可选择 `echo`，时间线里应看到类似 `start` → 文本类事件 → `done`。

## 菜单大概有什么

以当前导航为准（名字可能微调）：

| 菜单 | 用途 |
|------|------|
| 验证 | 运行黄金场景，分开展示业务结果与平台证据 |
| 插件调试 | 选 `route`、发消息、看事件时间线、工具轨迹与契约检查 |
| 总览 | 运行概况、基础设施状态 |
| 插件 | 看已注册业务插件 |
| 配置 | 调整安全的运行参数；保存前确认当前密码，其他部署/密钥配置只读 |
| Tools | 工具与权限相关 |
| Runs | 运行记录 |
| Prompts | 提示词 |
| 用量 | Token 用量 |
| 知识 | 知识后端状态 |

## 和 API 的关系

开发时，网页通过代理访问本机 API（默认 `127.0.0.1:8000`）。  
自动化测试、业务前端应携带合法认证上下文并**直接**调用 HTTP/SSE，不必经过 Web 控制台。

接口列表：[api-reference.md](../api-reference.md)。

控制台定位与架构边界见 [架构说明](../architecture.md)；插件调试方法见 [Plugin Playground](../plugin-playground.md)。

---

← [第一个插件](./04-first-plugin.md) · [文档目录](../INDEX.md)
