# AgentBridge

[English](README.md) · [文档目录](docs/INDEX.md) · [架构规则](AGENTS.md)

[![CI](https://github.com/Foamtor/AgentBridge/actions/workflows/ci.yml/badge.svg)](https://github.com/Foamtor/AgentBridge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](packages/core/pyproject.toml)

## 让 AI 按规则为现有业务系统编写工具与工作流

AgentBridge 是面向 Vibe Coding 的自托管业务 AI 开发底座。你和 AI 编程助手编写业务自己的 `domain` 与 `tools`；平台统一处理 JSON/SSE 契约、会话生命周期、权限、审批、审计和 RAG Port。

它是源码优先的底座：不是云端 Studio，不是已经完成的行业业务系统，也不会在不了解你的业务时自动生成可上线产品。

<!-- Compose 黄金案例落地后在此加入真实控制台截图。 -->

## 为什么需要 AgentBridge

给 ERP、工单、设备、客服或内部运营系统接入 AI 时，往往反复遇到同一批高风险公共问题：

- 流式输出如何保持顺序、可回放；
- 租户和权限上下文如何不被工具绕过；
- 写操作如何经过人工确认；
- RAG 如何进入真实业务流程；
- 平台公共代码和客户业务代码如何不互相污染。

AgentBridge 把这些问题统一收在平台层，业务代码则保留在插件式 domain 中。

| 你和 AI 编写 | AgentBridge 统一提供 |
| --- | --- |
| 业务流程、tools、权限、结构化返回 | JSON/SSE 信封、生命周期、取消、会话互斥 |
| 查询、表单、图表、台账数据 | 工具列表过滤与执行时再次鉴权 |
| 业务适配与展示消费者 | 审批、审计、租户上下文、RAG/DataSource Port |

## 工作方式

```text
现有业务系统
      │
      ├── AI 编写的 domain / tools / tests
      │
      ▼
AgentBridge API ── JSON + SSE ── 集成调试台 / 你的客户端
      │
      ├── 权限 · 审计 · 审批 · 生命周期
      └── DataSource / Retriever / LLM Gateway Port
```

架构刻意不让业务名称进入 `packages/core`。适配器只在 `apps/api/lifespan.py` 组装；domain 使用已注入的 Port，返回业务扩展事件，不直接推 SSE。

## 黄金案例：工单运营助手

[`work_order_ops`](apps/api/domains/work_order_ops/) 是真实业务闭环的参考实现，内置数据均为脱敏模拟数据。

1. 查询当前租户的工单；
2. 返回结构化列表、ECharts 配置和知识引用；
3. 填写工单与台账草稿并指派处理人；
4. 人工确认后才创建工单和台账；
5. 审批后的创建结果保持幂等。

控制台会展示 `x.work_order_ops.list`、`x.work_order_ops.chart`、`x.bridge.citation`、`x.bridge.approval_required` 等扩展事件的参考渲染方式。它不是客户最终使用的工单业务前端。

## 快速开始

v0.1.0 的主路径只有一条 Compose 命令：

```bash
docker compose up --build
```

启动后打开集成调试台，选择 `work_order_ops`。默认环境使用离线模型 Stub、fake knowledge、脱敏演示数据和开发租户；不要求模型密钥、外部 RAG 服务或 IdP。端口、重置说明和本地开发替代方式见[快速开始](docs/guide/02-quickstart.md)。

> 全栈 Compose 是 v0.1.0 的发布工作内容。其落地前，请使用现有的[本地开发指南](docs/guide/02-quickstart.md)。

## 用 AI 开发业务工具

在仓库根目录打开项目后，向 AI 编程助手发送：

```text
你在修改 AgentBridge。先读 AGENTS.md，再读
docs/ai-instructions/00-project-overview.md 与 01-architecture-rules.md。
新增业务能力时读 02-domain-development.md，并参考
apps/api/domains/work_order_ops 的真实模式，但不能把它的业务名复制进 packages/core。

实现前先定义输入、权限、结构化结果、审批/幂等需求和测试。domain 内不得创建
adapter，也不得直接推 SSE。没有权限的工具不能进入模型工具列表，调用时仍须再鉴权。

我的任务：<描述要新增的 domain 或 tool>
```

更多可复制配方（只读查询、列表/图表/台账、人工审批写操作）见[AI 编程手册](docs/ai-instructions/05-ai-coding.md)。

## 已有能力

| 领域 | 底座能力 |
| --- | --- |
| 对话运行 | FastAPI、LangGraph、稳定 SSE、取消、同会话协调 |
| 治理 | 租户上下文、工具列表过滤、执行期策略检查、审计、审批 |
| 业务接入 | domain 注册、DataSource/Retriever Port、结构化扩展事件 |
| 知识 | fake、pgvector、external 与可选只读 RAG-Agent 兼容后端 |
| 开发体验 | 集成调试台、TypeScript SDK、AI 可读规则、黄金案例 |

## 仓库结构

```text
packages/core/       可复用生命周期、Port、协议与适配器
apps/api/            FastAPI 宿主、组装根、路由和 domains
apps/api/domains/    业务插件；从 _scaffold 或 work_order_ops 开始
apps/web/            集成/调试控制台，不是客户业务前端
packages/sdk/        TypeScript 客户端
docs/                指南、契约、架构与 AI 手册
```

## 文档

- [快速开始](docs/guide/02-quickstart.md)
- [基本概念](docs/guide/03-concepts.md)
- [第一个 domain](docs/guide/04-first-plugin.md)
- [JSON 与 SSE 契约](docs/contracts.md)
- [不可违反的架构规则](AGENTS.md)
- [完整产品架构](docs/00-AgentBridge完整方案.md)
- [v0.1.0 首发范围](docs/superpowers/specs/2026-08-01-p3a-open-source-release-readiness-design.md)

## 状态与限制

AgentBridge 正在准备 **v0.1.0 技术预览**。它面向要在已有系统上构建 AI 层的开发者与团队。

- 默认演示故意离线，并只使用脱敏数据。
- 真实 LLM、外部 RAG、OIDC、多实例、部署迁移、备份恢复和生产稳定性仍是按需能力或延期工作。
- 可选 RAG-Agent 集成仅只读，并映射到固定演示租户；默认 Compose 不依赖它。
- 本次技术预览不发布 PyPI、npm、GHCR、签名镜像或企业供应链制品。

具体范围与延期的 P2-B 验证见[发布规划](docs/release-plan.md)。

## 贡献与安全

贡献必须遵守架构规则，并只提交脱敏示例数据。v0.1.0 社区文件落地后见 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [SECURITY.md](SECURITY.md)。

## 许可证

MIT，见 [LICENSE](LICENSE)。
