# 文档目录

按你是谁选入口。文档互相矛盾时，以 [完整方案](./00-AgentBridge完整方案.md) 为准。

## 人类入门（先看这里）

新人建议按 1→5 读完 `guide/`：第 2 篇就能跑通示例；后面几篇帮你分清三块东西、知道业务往哪加。  
（若接着自己加第一个插件，再加一点动手时间。）

| 文档 | 你读完会知道 |
|------|----------------|
| [根目录 README](../README.md) | 项目是什么、怎么约 5～10 分钟跑起来 |
| [1. 为什么用它](./guide/01-why.md) | 解决什么问题、边界在哪、适不适合你 |
| [2. 快速开始](./guide/02-quickstart.md) | 安装、启动、怎么确认成功 |
| [3. 基本概念](./guide/03-concepts.md) | domain、route、会话等词是什么意思 |
| [4. 第一个插件](./guide/04-first-plugin.md) | 自己的业务往哪放、怎么验收 |
| [5. AI 控制台](./guide/05-console.md) | 调试页边界、菜单；和业务前端的区别（快速开始里可能已用过） |

## AI 编程（给 Codex / Cursor / Claude 等助手）

| 文档 | 一句话 |
|------|--------|
| [AGENTS.md](../AGENTS.md) | 硬规则入口（与 CLAUDE.md 同步；任意工具可读） |
| [00 概览](./ai-instructions/00-project-overview.md) | 目录地图、权威优先级 |
| [01 架构规则](./ai-instructions/01-architecture-rules.md) | MUST、反模式、lifespan |
| [02 业务插件](./ai-instructions/02-domain-development.md) | 加插件检查清单 |
| [03 常见任务](./ai-instructions/03-common-tasks.md) | 可复制命令 |
| [04 测试](./ai-instructions/04-testing.md) | 测什么、环境变量坑 |
| [05 提示词与对话例](./ai-instructions/05-ai-coding.md) | 给人复制；**不绑某一家 IDE** |
| （可选）Cursor Skill | [`.cursor/skills/agentbridge-dev/SKILL.md`](../.cursor/skills/agentbridge-dev/SKILL.md) |

> 任意工具：先读 [AGENTS.md](../AGENTS.md) → [00](./ai-instructions/00-project-overview.md) → [01](./ai-instructions/01-architecture-rules.md)。人怎么喊助手见 [05](./ai-instructions/05-ai-coding.md)。

## 深度与归档

| 文档 | 什么时候打开 |
|------|----------------|
| [完整方案](./00-AgentBridge完整方案.md) | 要对齐产品约定、拍板架构 |
| [架构](./architecture.md) | 想看代码怎么分层 |
| [事件约定](./contracts.md) | 要对 SSE 事件字段 |
| [HTTP 接口](./api-reference.md) | 要对路由列表 |
| [部署](./deploy.md) | 要上 Postgres / 鉴权 / 生产单机 |
| [怎么加插件（细）](./add-a-domain.md) | 已经决定加插件，要逐步清单 |
| [知识库](./knowledge-base.md) | 检索与引用细节 |
| [路线图](./roadmap.md) | 做到哪一步了 |
| [发布规划](./release-plan.md) | v0.1.0 首发定位、范围与延期边界 |
| [v0.1.0 首发 Spec](./superpowers/specs/2026-08-01-p3a-open-source-release-readiness-design.md) | 当前唯一活动发布规格 |
| [v0.1.0 首发 Plan](./superpowers/plans/2026-08-01-p3a-open-source-release-preparation.md) | 当前唯一活动实施计划 |
| [v0.1.0 技术预览说明](./releases/v0.1.0-tech-preview.md) | 了解可体验能力、已知限制与公开发布前提 |
| [superpowers/](./superpowers/plans/README.md) | **历史**设计与分期计划（归档，日常别从这入门） |
