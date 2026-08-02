# AgentBridge v0.1.0 首次开源发布 Spec

> **状态：** 已结合现状与开源用途重写，待实施
>
> **版本：** `v0.1.0` 技术预览
>
> **性质：** 当前唯一活动发布 Spec；`docs/superpowers/` 其余 spec/plan 均为历史能力设计或实施记录

## 1. 发布定义

AgentBridge v0.1.0 是一个面向 Vibe Coding 的自托管业务 AI 开发底座。

它的标准使用方式是：

```text
clone / fork 仓库
  → 让 AI 阅读 AGENTS.md 与 ai-instructions
  → 参考 work_order_ops 黄金案例
  → 按规则编写 domain / tools / tests
  → 用一套 Docker Compose 启动 Web、API 与基础依赖
  → 在 AI 控制台验证 JSON / SSE / 权限 / 审批 / 业务结果
```

首版发布的核心承诺是“源码容易被人和 AI 理解、业务能力容易按规则扩展、整套开发体验能够跑起来”，不是公共 Python/npm 包，也不是无需二次开发的业务成品。

## 2. 目标用户

### 2.1 主要用户

- 想给已有 ERP、工单、设备、客服或内部管理系统增加 AI 对话能力的开发者；
- 使用 Codex、Claude Code、Cursor 等编码助手，通过自然语言改造业务系统的团队；
- 需要自托管、租户隔离、权限、审批、审计、RAG 与稳定 SSE 的集成开发者。

### 2.2 不适合的用户

- 只想注册账号后立即使用一个现成聊天产品；
- 期待仓库直接提供完整行业业务前端；
- 不准备阅读、修改或生成任何 domain/tools；
- 把技术预览当成已验证的生产高可用平台。

## 3. 首版对外价值

### 3.1 AI 编写业务，平台守住公共规则

| AI/开发者编写 | AgentBridge 统一提供 |
|---------------|----------------------|
| domain 流程、tools、业务输入与结构化结果 | JSON/SSE 契约、事件顺序、会话互斥、取消与回放 |
| 查询条件、业务权限声明、审批动作 | 工具列表过滤、执行期再次鉴权、租户上下文、审计 |
| 工单/订单/设备等业务适配 | DataSource/Retriever/Gateway 等 Port 与组装边界 |
| 列表、图表、台账等业务展示数据 | 扩展事件信封和 AI 控制台调试能力 |

### 3.2 黄金案例证明真实业务闭环

`work_order_ops` 是首版黄金案例，而不是产品附带的工单系统。它向 AI 展示：

- 查询租户内脱敏工单；
- 生成结构化列表和 ECharts 图表；
- 检索 SOP/FAQ 并返回 citation；
- 填写工单内容并指派处理人；
- 审批前生成台账预览；
- 人工批准后幂等创建工单和台账；
- 无权限工具不进入模型列表，执行时仍会再次鉴权。

RAG-Agent 仅作为真实业务形态参考和可选只读知识后端。默认体验不依赖 RAG-Agent 项目、真实数据库凭据或外部 Embedding 服务。

## 4. 首版范围

### 4.1 必须包含

1. 中英文 GitHub 首页；
2. 明确、唯一的 AI 读仓顺序和可复制 Vibe Coding 提示词；
3. 一套根目录 `docker-compose.yml`，默认启动 Web、API、PostgreSQL/pgvector；Redis 与 Authentik 仍在同一文件中按需开启；
4. 零模型密钥的真实平台流程体验；
5. 可视化工单黄金案例：列表、ECharts、citation、台账草稿和审批；
6. `CONTRIBUTING.md`、`SECURITY.md`、`CHANGELOG.md`、bug/PR 模板；
7. 现有架构/测试门禁和 Compose smoke；
8. 清晰的技术预览限制与 P2-B 延期说明。

### 4.2 明确不做

- PyPI、npm、GHCR 公共发布；
- wheel/sdist 作为独立交付产品；
- 云端 Studio、拖拽式 Agent 编排器；
- 客户业务系统的最终页面；
- 默认接入真实 LLM、RAG-Agent 或企业 IdP；
- 多机、高可用、备份恢复、跨版本升级回滚验收；
- SBOM、镜像签名或企业级供应链合规工程；
- 为首页数据好看而伪造 star、download、benchmark 或兼容性承诺。

## 5. 文档权威与历史归档

### 5.1 当前权威顺序

```text
AGENTS.md / CLAUDE.md                 硬规则
README.md / README.zh-CN.md           开源首页与首发入口
docs/ai-instructions/                 AI 开发手册
docs/guide/                           人类入门
docs/contracts.md                     JSON / SSE 契约
docs/00-AgentBridge完整方案.md         深层能力约定
本 Spec / 对应 Plan                   v0.1.0 首发范围与实施
docs/superpowers/ 其它文件             历史归档，仅供追溯
```

### 5.2 归档治理

首发前必须修复历史文档对 AI 的误导：

- `docs/superpowers/` 建立总入口，明确当前唯一活动 Spec/Plan；
- 旧文件统一标记“历史归档，不得直接执行”；
- 修复字面量 `\n\n` 归档提示；
- Plan6、Plan7、R-A、P1、P2-A 等更新为真实完成/归档状态；
- 修复工单 Spec “不接 RAG-Agent” 与后续只读集成的冲突；
- 移除或替换不存在的 `design-tracks`、`scheme-convergence` 等死链；
- 增加本地 Markdown 链接和归档状态检查。

历史内容无需重写成新产品文档；只需要让人和 AI 不会把旧计划当成当前任务。

## 6. GitHub 首页设计

### 6.1 语言策略

- `README.md`：英文主首页，便于 GitHub 国际用户发现与理解；
- `README.zh-CN.md`：完整简体中文镜像；
- 两份首页顶部互相切换：`English | 简体中文`；
- 核心章节、命令、链接、状态和限制保持语义一致；不要求机械逐字翻译；
- 用契约测试检查关键章节与链接同步。

### 6.2 Hero 文案基线

英文：

> **Build governed AI workflows on top of your existing business systems.**
>
> AgentBridge is a self-hosted, AI-readable foundation for Vibe Coding business tools—with streaming, permissions, approvals, audit, and RAG handled by the platform.

中文：

> **让 AI 按规则为现有业务系统编写工具与工作流。**
>
> AgentBridge 是面向 Vibe Coding 的自托管业务 AI 底座；流式、权限、审批、审计与 RAG 等公共能力由平台统一处理。

文案实施时可以润色，但不得改变“源码型底座、AI 编写业务、平台守公共规则”的含义。

### 6.3 首页结构

两份 README 使用相同的信息结构：

1. 语言切换、项目名、Hero、真实 CI/License/Python 徽章；
2. 一张真实 AI 控制台黄金案例截图；
3. “Why AgentBridge”：业务 AI 改造中重复出现的公共难题；
4. “How it works”：AI 写什么、平台负责什么的小图；
5. “Golden use case”：查询 → 图表 → 草稿 → 审批 → 工单/台账；
6. “Quick start”：`docker compose up --build`，然后打开 Web/API；
7. “Build with AI”：一段可复制的短提示词；
8. 核心能力表和小型架构图；
9. 文档导航；
10. Current status / limitations；
11. Contribution、Security、License。

### 6.4 视觉要求

- 只展示真实功能截图，不使用与实现不符的概念图；
- 截图应包含工单列表、ECharts 图表、台账/审批区域中的至少两项；
- 图片放在 `docs/assets/`，压缩到适合 GitHub 加载的大小；
- 首屏不堆砌长表格、内部里程碑编号或十几个徽章；
- 不把 `apps/web` 描述为客户业务前端，它是集成开发者的 AI 控制台；
- README 正文建议控制在约 180–260 行/语言，深层细节链接到 docs。

## 7. 一套 Compose 的首发体验

### 7.1 默认服务

| 服务 | 默认职责 |
|------|----------|
| `web` | 构建并提供 AI 控制台，通过同源 `/api` 访问后端 |
| `api` | 从仓库源码安装并启动 FastAPI/LangGraph |
| `postgres` | PG16 + pgvector；初始化脱敏演示数据和审批表 |
| `redis` | 可选 profile；供用户验证 Redis 锁/限流，不增加默认体验负担 |

Redis 与 Authentik 可继续作为同一个 Compose 文件中的可选 profile，但不进入默认首发命令。PostgreSQL 默认只在 Compose 网络内暴露；如需宿主机调试，使用显式可配置端口，避免与用户已有的 5432 实例冲突。

### 7.2 默认运行配置

默认 Compose：

- 不启用 `AGENTBRIDGE_FAKE_RUNTIME`，运行真实 Lifecycle + LangGraph；
- LLM Gateway 继续使用仓库内离线 FakeChatModel，因此不需要模型密钥；
- `KNOWLEDGE_BACKEND=fake`，因此不需要 Embedding 或 RAG-Agent；
- 开启 Postgres DataSource 和 Postgres ApprovalStore；
- `AUTH_REQUIRED=false`，开发上下文为 `tenant_id=dev`、admin、`permissions=["*"]`；
- 新增幂等 migration，为 `dev` 租户提供脱敏工单、处理人和台账数据。
- Redis 锁/限流保持可选；默认单进程体验使用内存实现。

这样默认环境能够真实执行工单查询、统计、结构化审批草稿和批准后的数据库写入，而不是只返回一条固定的 `ok`。

### 7.3 首发命令与成功标准

```bash
docker compose up --build
```

成功标准：

- Web 可访问；
- API `/health`、`/ready` 成功；
- 控制台能选择 `work_order_ops`；
- “查看工单”产生列表和图表；
- 结构化创建示例产生台账预览与审批；
- 点击批准后产生创建结果，重复批准不重复写入；
- `docker compose down` 只停止本项目栈。

数据库初始化脚本只对新 volume 自动执行；已有 volume 的升级不在首版承诺内，文档必须给出明确的演示数据重置方式并提醒会删除本地演示 volume。

## 8. 黄金案例控制台

`apps/web` 在首版增加通用的扩展事件渲染示例：

- `x.work_order_ops.list` → 表格；
- `x.work_order_ops.chart` → 使用后端 `echarts_option` 渲染；
- `x.bridge.citation` → 引用列表；
- `x.work_order_ops.ledger_preview` → 台账/工单草稿卡片；
- `x.bridge.approval_required` → 审批区域；
- `x.work_order_ops.work_order_created` → 创建成功结果。

这些组件是“如何消费业务扩展事件”的参考实现。事件类型不认识时仍回退到通用 JSON/时间线，不把 `work_order_ops` 写入 core。

控制台提供零密钥演示预设：

- 查看脱敏工单；
- 生成饼图/柱状图；
- 使用结构化 `extra.work_order_draft` 创建审批草稿；
- 批准或拒绝。

## 9. AI/Vibe Coding 开发入口

首版 README 的短提示词应让 AI：

1. 先读 `AGENTS.md`；
2. 再读 `00-project-overview`、`01-architecture-rules`、`02-domain-development`；
3. 参考 `work_order_ops`，但不复制其业务名到 core；
4. 为新业务声明 tools、权限、结构化返回和测试；
5. 写操作使用平台审批；
6. 不在 domain 创建 adapter 或直接推 SSE；
7. 运行最低验证命令并报告结果。

AI 手册至少提供三类可复制任务：

- 新增只读查询 tool；
- 新增列表/统计图表/台账输出；
- 新增需要人工审批的写 tool。

## 10. 基础开源卫生

首版只补必要文件：

- `CONTRIBUTING.md`：开发入口、MUST、测试、脱敏与 PR 要求；
- `SECURITY.md`：提醒不要公开密钥、真实数据或漏洞细节，提供可维护的联系路径；
- `CHANGELOG.md`：记录 v0.1.0 已有能力与已知限制；
- bug report 与 PR template；
- MIT LICENSE 保持现状。

不以 CODE_OF_CONDUCT、公共 registry、SBOM、签名或外部安全平台设置阻塞 v0.1.0 技术预览。

## 11. 验收标准

### 11.1 首页

- 英文、中文 README 均完整可读、互相链接；
- Hero 在一分钟内说明是什么、适合谁、怎样开始；
- 截图和徽章都对应真实仓库状态；
- Quick Start 只有一条主命令；
- 首屏突出 Vibe Coding、domain/tools 和黄金案例，不突出内部 M0–M12 排期。

### 11.2 体验

- 干净演示环境执行 `docker compose up --build` 能启动完整栈；
- 默认无外部模型/RAG 凭据也能走真实平台流程；
- 工单列表、图表、草稿、审批、创建和台账闭环可演示；
- Compose smoke 自动验证关键 HTTP/业务结果，并安全清理专属测试栈。

### 11.3 AI 开发

- 新对话只按公开读序即可定位 domain/tools 修改点；
- 示例提示词不会诱导 AI 修改 core、直接使用 adapter 或绕过权限；
- 文档链接和归档状态检查通过；历史计划不会被误认为当前任务。

### 11.4 质量与口径

- AGENTS 规定的三项最低门禁通过；
- core/API、SDK/Web、eval、Ruff 和 Compose smoke 通过；
- README、完整方案、路线图、发布规划、release notes 对首发定位一致；
- P2-B、多机和生产稳定继续标为延期/非承诺；
- 不发布 PyPI/npm/GHCR，不创建正式 tag；正式 GitHub Release 在本计划完成并合入后单独执行。
