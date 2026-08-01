# P2-A 运行、安全、RAG 与控制台验收记录

> **状态：** 进行中。此记录只公开脱敏后的命令、版本、数量和结论；它不是生产部署、具体 IdP 认证或多机验收证据。

## 脱敏规则

- 不记录连接串、口令、令牌、私钥、向量、业务正文、用户原文或完整模型输出。
- 只记录依赖名称、版本、命令、状态码、测试数量、事件类型和错误码。
- 发现敏感内容时，删除该内容后重新生成记录；不在本文件中以掩码形式保留原值。

## 范围与 P2-B 延期项

P2-A 覆盖认证与授权、RAG 后端契约、运行故障语义和控制台构建/权限闭环。

P2-B 仍需完成：干净环境部署、迁移与升级/回滚、备份恢复、具体身份提供方现场登录、厂商 external RAG 联调，以及双实例 Redis 锁和跨实例限流。

## 环境与版本

| 字段 | 当前记录 |
|---|---|
| 分支与基线提交 | `codex/p2a-release-validation`；待 A9 汇总最终 SHA |
| Python | 3.12.13（本地 `.venv`） |
| Node / npm | 22.14.0 / 10.9.2 |
| PostgreSQL 测试库 | `agentbridge_test`；专用角色存在；连接信息未记录 |
| Embedding 服务 | 本地 TEI 端口可达；模型/维度待 A4 记录 |
| RAG-Agent | 只读探针待 A4；连接信息未记录 |

## 命令与结果

| 时间 | 命令类别 | 结果 | 摘要 |
|---|---|---|---|
| A0 | 核心 + API 联合 pytest | pass | 340 passed, 7 skipped；1 条既有 Starlette/httpx 弃用警告 |
| A0 | 架构门禁 | pass | import-linter、core scan、RAG scan 均通过 |
| A0 | Web build | pass | Node 22.14.0 下 `npm ci` 与 `npm run build` 通过 |
| A0 | 全仓 Ruff 基线 | recorded | 61 条既有债务；P2-A 仅要求变更路径为零，清零移交 P3 |

## 任务状态

| 任务 | 状态 | 证据 / 阻塞 |
|---|---|---|
| A0 | complete | 分支、环境、联合门禁与 Web build 已完成 |
| A1 | complete | 证据契约测试、脱敏检查与新增路径 Ruff 已通过 |
| A2 | complete | HS256、受控 JWKS、身份声明拒绝与零副作用测试通过 |
| A3 | pending | 授权、租户隔离、审批与审计 |
| A4 | pending | pgvector 与只读 RAG-Agent；需要安全注入测试连接 |
| A5 | pending | external RAG HTTP contract |
| A6 | pending | 取消、EventLog 与审批投递 |
| A7 | pending | 单机限流与 readiness |
| A8 | pending | Vitest、控制台与 CI |
| A9 | pending | 全量复核与发布口径 |

## 阻塞项与已知限制

- A4 尚未注入专用 pgvector 测试连接和只读 RAG-Agent 连接；不能以 fake 结果替代。
- P2-B 延期项不计入 P2-A 完成，也不改变技术预览口径。
- 全仓 Ruff 债务未清零；每个 P2-A 变更路径仍必须通过 Ruff。

## 复核

| 项目 | 复核结果 | 复核人 / 时间 |
|---|---|---|
| A0 环境与门禁 | pass | Codex / 2026-08-01 |
| A1 证据契约 | pass | Codex / 2026-08-01 |
| A2 JWT / JWKS middleware | pass | Codex / 2026-08-01 |
| A3–A9 | pending | 待实施 |
