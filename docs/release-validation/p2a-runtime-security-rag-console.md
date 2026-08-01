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
| PostgreSQL 测试库 | 独立可销毁 pgvector 容器；连接信息未记录 |
| Embedding 服务 | 本地兼容服务可达；`BAAI/bge-m3`，512 维 |
| RAG-Agent | 只读探针待 A4；连接信息未记录 |

## 命令与结果

| 时间 | 命令类别 | 结果 | 摘要 |
|---|---|---|---|
| A0 | 核心 + API 联合 pytest | pass | 340 passed, 7 skipped；1 条既有 Starlette/httpx 弃用警告 |
| A0 | 架构门禁 | pass | import-linter、core scan、RAG scan 均通过 |
| A0 | Web build | pass | Node 22.14.0 下 `npm ci` 与 `npm run build` 通过 |
| A0 | 全仓 Ruff 基线 | recorded | 61 条既有债务；P2-A 仅要求变更路径为零，清零移交 P3 |
| A4 | 平台 pgvector live | pass | 独立容器；同租户 citation、跨租户零命中；不记录文档或向量 |
| A9（预检） | 全量 Python/架构/Web 门禁 | pass | 354 passed，7 skipped；变更路径 Ruff、架构扫描、Web test/build 均通过 |

## 任务状态

| 任务 | 状态 | 证据 / 阻塞 |
|---|---|---|
| A0 | complete | 分支、环境、联合门禁与 Web build 已完成 |
| A1 | complete | 证据契约测试、脱敏检查与新增路径 Ruff 已通过 |
| A2 | complete | HS256、受控 JWKS、身份声明拒绝与零副作用测试通过 |
| A3 | complete | 权限、租户隔离、审批、审计矩阵与脱敏摘要脚本通过 |
| A4 | pending | 独立 pgvector live 检索、同租户 citation 与跨租户零命中已通过；只读 RAG-Agent DSN 仍未安全注入 |
| A5 | complete | MockTransport 协议、失败策略、501 与 citation 矩阵通过；厂商现场联调仍属 P2-B |
| A6 | complete | 取消、EventLog 顺序、投递失败与审批幂等矩阵通过（43 passed，1 skipped） |
| A7 | complete | 单机限流、窗口恢复与 readiness/status 安全矩阵通过（10 passed） |
| A8 | complete | Node 22.14 下 Vitest（6 tests）、build、控制台 stream→replay→audit 闭环与 CI job 通过 |
| A9 | pending | 全量复核与发布口径 |

## 阻塞项与已知限制

- A4 的独立 pgvector 测试容器已完成平台真检索验收；只读 RAG-Agent 连接尚未由安全环境注入，不能以 fake 结果替代该 probe。
- P2-B 延期项不计入 P2-A 完成，也不改变技术预览口径。
- 全仓 Ruff 债务未清零；每个 P2-A 变更路径仍必须通过 Ruff。

## 复核

| 项目 | 复核结果 | 复核人 / 时间 |
|---|---|---|
| A0 环境与门禁 | pass | Codex / 2026-08-01 |
| A1 证据契约 | pass | Codex / 2026-08-01 |
| A2 JWT / JWKS middleware | pass | Codex / 2026-08-01 |
| A3 授权与审计 | pass | Codex / 2026-08-01 |
| A5 external RAG contract | pass | Codex / 2026-08-01；18 passed，vendor-live deferred to P2-B |
| A6 lifecycle and delivery | pass | Codex / 2026-08-01；43 passed，1 skipped |
| A7 single-node readiness | pass | Codex / 2026-08-01；10 passed；不含 Redis/多机结论 |
| A8 web console | pass | Codex / 2026-08-01；Vitest 6 passed、build 通过、闭环仅输出状态与数量 |
| A4 platform pgvector | pass | Codex / 2026-08-01；独立容器、512 维本机 embedding、同租户 citation/跨租户隔离通过 |
| A4 RAG-Agent probe、A9 | pending | 待实施 |
