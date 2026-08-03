<div align="center">

# AgentBridge

🔌 **给你的业务系统加上 Agent 能力——知识检索、数据分析、结构化输出、人工审批——不改一行现有代码。**

面向 [Vibe Coding](#-用-vibe-coding-方式接入你的业务系统)：让 AI 编程助手帮你写插件，几分钟接好。

[English](README.md) · [文档](docs/INDEX.md) · [架构规则](AGENTS.md) · [Vibe Coding 接入指南](SKILL.md)

[![CI](https://github.com/Foamtor/AgentBridge/actions/workflows/ci.yml/badge.svg)](https://github.com/Foamtor/AgentBridge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](packages/core/pyproject.toml)

</div>

---

> 不管你的业务系统是政务平台、企业 ERP、设备管理还是内部运营工具，只要它有 API 或数据库，AgentBridge 就能在它旁边加一层 Agent 能力：用户用自然语言描述需求，Agent 根据业务数据动态生成表格、图表、分析报告，需要写操作时走人工审批。
>
> **不动现有系统，不迁移数据，不依赖云服务。** 装在你自己的机器上，MIT 开源。

<!-- TODO: 录 GIF demo → docker compose up → 浏览器 → 输入需求 → 动态生成结果 -->
<!--
<p align="center">
  <img src="docs/assets/demo.gif" alt="AgentBridge Demo" width="700" />
</p>
-->

## 🏗️ 怎么做到不改现有代码

AgentBridge 不碰你的业务系统。它在你现有接口旁边加一层适配——你写一个插件描述你的 API 能做什么，AgentBridge 负责让 Agent 能调用它，并管好权限、审批、审计这些公共的事。

<p align="center">
  <img src="docs/assets/architecture.png" alt="AgentBridge 分层架构" width="800" />
</p>

你写插件，平台管剩下的事：

| ✏️ 你写的 | 🔧 平台管的 |
|-----------|------------|
| 你的 API 有哪些能力、要什么参数、返回什么格式 | 对话管理、流式输出、会话状态 |
| 业务数据怎么查、怎么分析 | 权限校验、租户隔离、工具过滤 |
| 知识库挂哪里、结构化结果长什么样 | 人工审批、操作审计、取消和恢复 |

## 🤖 用 Vibe Coding 方式接入你的业务系统

AgentBridge 是为 Vibe Coding 设计的。你不需要自己写代码——让 Cursor、Codex、Claude Code 等 AI 编程助手帮你写插件。

**三个步骤：**

1. Clone 仓库，用你的 AI 编程助手打开
2. 把 [`SKILL.md`](SKILL.md) 的内容喂给助手（或让助手自己读）
3. 告诉助手你的业务系统有什么接口，它帮你写好插件

```
读 SKILL.md，然后帮我接入业务系统。

我的系统：<一句话描述你的系统是做什么的>
我的接口：<列出你的 API 或数据库表>
用户会问什么：<举几个实际的例子>
```

详细的接入指南和可复制的提示词见 [`SKILL.md`](SKILL.md)。

## 🎯 适合什么时候用

你已经有 API 或数据库，想给系统加上 Agent 能力验证效果——不管是做个原型给领导看，还是真的上线给业务人员用。

- 🔍 **产品验证**：快速让老板/客户看到"我们的系统能用 AI 做数据分析"
- ⚡ **内部提效**：给已有的审批、查询、报表系统加一个自然语言入口
- 🔗 **能力复用**：多个业务系统共用一套权限、审批、审计，不用每个系统单独做

## ⚠️ 不适合什么时候用

- 🚫 从零造一个 AI 产品（没有现有 API）→ 直接用 LangGraph、CrewAI 这类框架
- 🚫 高频实时交易（Agent 有 1-3 秒推理延迟）→ 传统 API 网关更合适
- 🚫 替代整套账号体系 → AgentBridge 能对接你已有的登录系统，但不替代它
- 🚫 开箱即用的多机扩展 → 需要按文档配置，不是默认支持

简单判断：你的系统有 API，你想让 AI 能调用这些 API 并且需要权限和审批——用 AgentBridge。你从零开始造 AI 产品——不需要。

## 🚀 跑起来看效果

```bash
git clone https://github.com/Foamtor/AgentBridge.git
cd AgentBridge
docker compose up --build
```

打开 `http://localhost:8080`，选 `work_order_ops`，开始体验。
如设置了 `WEB_PORT`，请使用对应端口。

> 💡 跑起来不需要 API Key，不需要外部数据库，不需要云服务。内置了离线模型和脱敏的演示数据，纯粹为了让你看到效果。
>
> 详细说明见[快速开始指南](docs/guide/02-quickstart.md)。

## 📋 一个完整的例子

仓库里有一个叫 `work_order_ops` 的参考实现，展示了一个完整的业务闭环：从查数据到审批后创建记录。

| 👤 用户 | 🤖 系统 |
|---------|---------|
| "查一下本月工单" | 查询业务数据库，动态生成表格和图表 |
| "搜一下处理规范" | 从知识库检索相关内容，标注来源 |
| "帮我建一个工单" | 根据对话内容生成工单草稿，等你确认 |
| — | 弹出审批提示，等你决定 |
| "批准" | 执行创建，结果幂等——不会重复建 |

用的都是脱敏的模拟数据。它不是最终产品——是你写自己业务插件时可以照着改的模板。

## 📦 平台做了什么

| 能力 | 具体做了什么 |
|------|-------------|
| 🤖 Agent 运行时 | 理解用户意图，决定调哪些接口，把结果组织成用户能看懂的格式 |
| 📚 知识检索 | 业务知识库接入，回答问题时引用来源 |
| 🔒 权限控制 | 不同用户看到不同数据，工具调用前再次校验权限 |
| ✅ 人工审批 | 涉及写操作时必须人工确认，确认后幂等执行 |
| 📋 操作审计 | 每次调用都有记录，可追溯 |
| 📊 结构化输出 | 动态生成表格、图表、台账、审批单——不是只有文字 |
| 🧩 插件隔离 | 你的业务代码和平台代码各管各的，互不干扰 |

## 🗂️ 仓库结构

```
packages/core/          平台核心：生命周期、协议、适配器
apps/api/               服务入口：路由、组装
│   └── domains/        业务插件放这里
│       ├── _scaffold/  插件模板
│       └── work_order_ops/  参考实现
apps/web/               调试控制台
packages/sdk/           TypeScript 客户端
docs/                   文档
SKILL.md                Vibe Coding 接入指南（喂给 AI 助手用）
```

## 📊 当前状态

- 🚧 v0.1.0 技术预览准备中
- ✅ 默认 Compose 黄金流程已完成本地验收
- ✅ 包含可运行的 `work_order_ops` 参考实现
- ⚠️ CI 遗留问题正在清理
- 🚧 生产 IdP、多机验证、迁移恢复和包发布尚未完成

## 🤝 参与贡献

1. Fork → 创建分支 → 提交 PR
2. 阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解代码规范
3. 只使用脱敏示例数据，不提交真实业务数据

## 📄 许可证

MIT © [Foamtor](https://github.com/Foamtor)

---

<div align="center">

**觉得有用？点个 ⭐ Star 支持一下！**

[![Star History Chart](https://api.star-history.com/svg?repos=Foamtor/AgentBridge&type=Date)](https://star-history.com/#Foamtor/AgentBridge&Date)

</div>
