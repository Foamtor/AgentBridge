# 项目概览（给 AI 助手）

**你在改 AgentBridge：** 自托管（装在客户自己环境）的 AI 对话接入底座。  
业务做成 `apps/api/domains/` 下的插件；流式、会话等公共事先由平台管。

入口硬规则：仓库根目录 [`AGENTS.md`](../../AGENTS.md)（与 `CLAUDE.md` 同步）。

## 权威怎么用（别搞混）

| 冲突类型 | 以谁为准 |
|----------|----------|
| 产品约定 / 架构拍板 | `docs/00-AgentBridge完整方案.md` |
| 写代码时的分层禁令 | `AGENTS.md`（应与完整方案一致；若发现不一致，**改文档**对齐完整方案，不要先违 MUST） |
| 人类怎么入门 | `docs/guide/` + 根 `README.md` |
| 本目录 | 任务清单与命令；**不发明**新硬规则（细则只能解释 AGENTS） |
| `docs/superpowers/` | 历史设计/计划，**勿当现行规格** |

## 仓库三块（别混）

| 块 | 路径 | 说明 |
|----|------|------|
| 底座 | `packages/core` + `apps/api` 的平台部分 | 编排、约定、HTTP |
| 业务插件 | `apps/api/domains/<名字>/` | 一个文件夹 ≈ 一个请求里的 `route` |
| 调试台 | `apps/web` | 集成方调试用，**不是**客户业务前端 |

`apps/api` 里既有平台服务，也有 `domains/`。改业务优先只动 `domains/`。

## 目录速查

```text
packages/core/src/agentbridge_core/
  application/   # 流程层 — 禁止直接 import adapters
  ports/         # 接口约定
  adapters/      # 核心侧适配器实现（由 lifespan 创建/注入）
apps/api/lifespan.py     # 组装根：创建适配器、注册 domain
apps/api/adapters/       # API 侧适配器/工厂（同样只由 lifespan 调用接线）
apps/api/domains/<name>/ # 业务插件（echo、demo_*、_scaffold）
apps/api/routes/         # HTTP；可组装 sink 交给生命周期（不是 domain）
apps/web/                # AI 控制台
docs/guide/              # 人类白话
docs/ai-instructions/    # 本手册
docs/contracts.md        # SSE 事件约定
docs/add-a-domain.md     # 加插件逐步清单
```

## 包名与常见环境变量

- 代码 import：`agentbridge_core`；发行名常写作 `agentbridge-core` / `agentbridge-api`
- `AGENTBRIDGE_FAKE_RUNTIME`：测试用假运行时（见 `04-testing.md`）
- `KNOWLEDGE_BACKEND`：`fake` / `langchain_pg` / `external`（见 `03`、`.env.example`）

## 本手册读序

| 顺序 | 文件 | 何时 |
|------|------|------|
| 0 | [`AGENTS.md`](../../AGENTS.md) | 任何改动前 |
| 1 | 本文（00） | 摸清地图与权威 |
| 2 | [01-architecture-rules](./01-architecture-rules.md) | 硬规则展开与反模式 |
| 3 | [02-domain-development](./02-domain-development.md) | **仅当**加/改业务插件 |
| 4 | [03-common-tasks](./03-common-tasks.md) | 需要可复制命令时 |
| 5 | [04-testing](./04-testing.md) | 跑测、防 `.env` 坑（可单读） |
| — | [05-ai-coding](./05-ai-coding.md) | **给人**：提示词与对话例（Codex / Cursor / Claude 等通用） |

人类场景感：[guide/](../guide/README.md) · 总目录：[INDEX](../INDEX.md)  
Cursor 可选：`.cursor/skills/agentbridge-dev/SKILL.md`（没有 Cursor 不影响，用 05 的开场模板即可）
