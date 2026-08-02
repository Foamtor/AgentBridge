# AgentBridge v0.1.0 首次开源发布 Implementation Plan

> **状态：** 已按首发目标重写并完成书面复核，待实施
>
> **分支：** `codex/p3a-release-preparation`（普通 Git 分支，不使用 worktree）
>
> **Spec：** [AgentBridge v0.1.0 首次开源发布 Spec](../specs/2026-08-01-p3a-open-source-release-readiness-design.md)
>
> **执行方式：** 当前会话内联分批；每个任务实现、测试、复核后再继续

**Goal:** 发布一份像样、可信、可运行的源码型开源技术预览：中英文首页有吸引力，AI 能按规则编写 domain/tools，一套 Compose 能展示工单查询、图表、台账和审批闭环。

**Non-goals:** 不发布 PyPI/npm/GHCR；不做生产部署、迁移恢复、多机或具体 IdP 验收；不把 AgentBridge 包装成无需二次开发的业务成品。

## 1. 任务依赖

| 任务 | 内容 | 依赖 |
|------|------|------|
| A0 | 收敛权威文档与历史归档 | 无 |
| A1 | 中英文 GitHub 首页骨架与品牌表达 | A0 |
| A2 | 一套全栈 Compose 与脱敏演示数据 | A0 |
| A3 | 可视化工单黄金案例与零密钥演示 | A1、A2 |
| A4 | AI/Vibe Coding 的 tools 开发入口 | A0、A3 |
| A5 | 开源卫生、CI、首页定稿与首发复核 | A1–A4 |

## 2. 全局约束

- 不直接在 `main` 实施，不使用 worktree。
- AGENTS/CLAUDE 正文保持同步。
- 业务演示只使用 `apps/api/domains/work_order_ops` 和脱敏 `dev` 租户数据；不得把业务名写入 core。
- domain 不持有 EventSink，不创建 adapter；适配器仍只在 composition root 组装。
- 默认 Compose 不需要 LLM API key、Embedding、RAG-Agent DSN 或 OIDC。
- 不提交 `.env`、真实凭据、真实业务数据、数据库 volume 或本地构建产物。
- Docker smoke 使用唯一 Compose project name；只清理它创建的容器、网络和演示 volume。
- 每个任务提交前先审阅 diff、跑任务级测试；A5 再跑全量门禁。

## 3. 任务详单

### Task A0：收敛唯一权威路径和历史归档

**Files:**

- Modify: `docs/00-AgentBridge完整方案.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/release-plan.md`
- Modify: `docs/INDEX.md`
- Create: `docs/superpowers/README.md`
- Modify: `docs/superpowers/plans/README.md`
- Modify: `docs/superpowers/specs/*.md`（历史状态/死链机械修订；本 Spec 除外）
- Modify: `docs/superpowers/plans/*.md`（历史状态/死链机械修订；本 Plan 除外）
- Create: `scripts/check_release_docs.py`

**Steps:**

1. 在完整方案最前面增加当前首要用途：面向 Vibe Coding 的源码型业务 AI 底座；标准旅程是 clone/fork → AI 读规则 → 编写 domain/tools → Compose 验证。
2. 保留已有能力架构，但把 SDK、多 Agent、多机、控制台治理明确标成进阶/可选能力，不作为新人首发路径。
3. 路线图和发布规划把 `v0.1.0` 定义为当前源码快照的首次技术预览；不再让早期 v0.x/v2.1 能力标签抢占首页口径。
4. 新建 `docs/superpowers/README.md`：本 Spec/Plan 是唯一活动发布文档，其余文件均为历史参考，不得直接执行。
5. 给旧 spec/plan 加统一归档 banner，修正真实状态；移除残留的 agent 执行指令和字面量 `\n\n`。
6. 修复 20 组已知死链：链接到仍存在的权威文档，或改成不带链接的历史决策说明；不创建空壳文件骗过检查。
7. 修订工单黄金案例 Spec：默认使用仓库脱敏数据；RAG-Agent 是后续已完成的可选只读后端，不再写成绝对“不接入”。
8. 一个轻量发布文档脚本检查本地 Markdown 链接、归档 banner、唯一活动计划、README 语言互链、AGENTS/CLAUDE 同步及 P2-A/P2-B 状态；不对营销文案逐字或按行数设硬门槛。

**Verify:**

```powershell
.\.venv\Scripts\python.exe scripts/check_release_docs.py
bash scripts/check_ai_instructions.sh
git diff --check
```

**Review checkpoint:** 确认旧文档只被降权和纠错，没有删除仍有价值的架构决策。

**Commit:** `docs: converge v0.1 release authority`

### Task A1：设计并建立中英文 GitHub 首页

**Files:**

- Rewrite: `README.md`（英文主首页）
- Create: `README.zh-CN.md`（完整中文镜像）
- Create: `docs/assets/README.md`（截图来源与更新说明）
- Modify: `docs/INDEX.md`

**Steps:**

1. 英文 README 使用 Spec §6 的 Hero 基线；中文 README 使用对应中文表达。顶部提供 `English | 简体中文` 切换。
2. 只加入真实徽章：GitHub Actions CI、MIT、Python 3.12+；Node 写主验证版本 22.14，不制作下载量/覆盖率假徽章。
3. 两份 README 按同一顺序建立章节：Why、How it works、Golden use case、Quick start、Build with AI、Capabilities、Architecture、Docs、Status、Contributing/Security/License。
4. Quick Start 的唯一主路径为 `docker compose up --build`；A2 完成前将截图位置标成待 A5 补齐的内部注释，不能提交破图或虚构 UI。
5. “Build with AI” 放一段不超过约 15 行的复制提示词；更长配方链接 A4 的 AI 手册。
6. 用紧凑 Mermaid 或文本图表达：业务系统 → AI 编写的 domain/tools → AgentBridge 公共生命周期 → Web/API 客户端。
7. README 明确 AI 控制台不是客户业务前端，v0.1.0 不是生产高可用承诺。
8. `check_release_docs.py` 检查语言互链、主 Compose 命令、黄金案例入口、AI 提示词入口、限制与所有本地链接；章节标题和营销文案保留可编辑空间。

**Verify:**

```powershell
.\.venv\Scripts\python.exe scripts/check_release_docs.py
rg -n "Vibe Coding|docker compose up --build|work_order_ops|AGENTS.md|Technical Preview" README.md
rg -n "Vibe Coding|docker compose up --build|work_order_ops|AGENTS.md|技术预览" README.zh-CN.md
git diff --check
```

**Review checkpoint:** 以第一次访问 GitHub 的开发者视角检查：一分钟能否理解价值，是否先看到用途和演示而非内部架构编号。

**Commit:** `docs: add bilingual open source homepage`

### Task A2：实现一套全栈 Compose 与脱敏 dev 数据

**Files:**

- Create: `Dockerfile`
- Create: `apps/web/Dockerfile`
- Create: `apps/web/nginx.conf`
- Create: `.dockerignore`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Create: `apps/api/migrations/008_v01_demo.sql`
- Modify: `apps/api/migrations/README.md`
- Modify: `docs/deploy.md`
- Modify: `docs/guide/02-quickstart.md`
- Create: `scripts/verify_compose_stack.py`

**Steps:**

1. API Dockerfile 从仓库源码安装 core 与 API 的运行依赖，使用 `uvicorn` 启动；不增加公共 wheel 发布流程。
2. Web Dockerfile 使用 Node 22.14 构建，再用轻量 Web server 提供静态资源；构建时设置 `VITE_API_BASE=/api`。
3. Web server 将 `/api/*` 同源反代到 API，并支持 BrowserRouter fallback；不得在浏览器写死 `127.0.0.1:8000`。
4. Compose 默认启动 `web`、`api`、`postgres`；Postgres 改为 PG16 + pgvector 镜像。Redis 与 Authentik 若保留，使用可选 profile，不能增加默认首发命令的资源和配置负担。
5. PostgreSQL 默认只供 Compose 内部访问；宿主机数据库端口如需开放必须可配置且默认不占用 5432。
6. 新 Postgres volume 按顺序加载现有幂等 migrations；新增 `008_v01_demo.sql` 为 `tenant_id=dev` 创建脱敏处理人、工单和台账种子，不修改其它演示租户。
7. API 默认运行真实 Lifecycle/LangGraph，使用离线 FakeChatModel、Fake knowledge、Postgres DataSource、Postgres ApprovalStore、开发级无认证上下文和内存 checkpointer。
8. healthcheck 和 `depends_on` 只表达真实依赖；API readiness、Web 页面均须在 smoke 中验证。
9. `verify_compose_stack.py` 使用唯一 project name 执行 config/build/up/poll/smoke/down；只有显式 `--remove-demo-volume` 才删除其专属测试 volume。
10. 文档说明首次初始化、端口、查看日志、停止服务和重置脱敏演示 volume；重置命令旁明确数据删除影响。

**Verify:**

```powershell
docker compose config --quiet
.\.venv\Scripts\python.exe scripts/verify_compose_stack.py --remove-demo-volume
```

**Review checkpoint:** 确认 Compose 只是一套源码体验环境，没有声称完成 P2-B 生产部署、升级或多机验证。

**Commit:** `build: add zero-key full stack demo`

### Task A3：实现可视化工单黄金案例

**Files:**

- Modify: `apps/web/package.json`
- Modify: `apps/web/package-lock.json`
- Modify: `apps/web/src/features/debug/DebugPage.tsx`
- Modify: `apps/web/src/features/debug/SessionBar.tsx`
- Modify: `apps/web/src/features/debug/EventTimeline.tsx`
- Create: `apps/web/src/features/debug/GoldenCasePanel.tsx`
- Create: `apps/web/src/features/debug/GoldenCasePanel.test.tsx`
- Modify: `apps/web/src/features/debug/DebugPage.test.tsx`
- Modify: `apps/web/src/styles.css`
- Modify: `scripts/verify_compose_stack.py`
- Modify: `apps/api/domains/work_order_ops/README.md`
- Create: `apps/api/tests/test_v01_golden_demo.py`

**Steps:**

1. 调试页增加黄金案例预设：查看工单、生成饼图、创建结构化工单草稿。预设可见地展示其请求，不隐藏 `extra.work_order_draft`。
2. 发送接口支持可选 `extra`，普通 route 行为保持兼容。
3. `GoldenCasePanel` 解析并渲染 list 表格、ECharts option、citation、ledger preview、approval required 和 created result。
4. ECharts 只消费后端返回的 `echarts_option`；非法或未知 option 回退到无执行能力的列表/JSON，不运行任意脚本。
5. 审批按钮调用现有 approval API，支持 approve/deny，展示 pending/succeeded/denied/error；重复点击不能造成重复业务写入。
6. 未知 `x.*` 事件仍由通用 EventTimeline 折叠展示，组件不是新的业务协议真源。
7. API/Compose smoke 依次验证 `dev` 租户：列表与图表 → 结构化草稿与审批事件 → approve → 创建结果 → 重复 approve 无重复行。
8. 更新黄金案例 README，提供 Web 操作步骤、curl JSON、事件与源码位置，说明 RAG-Agent 是可选只读进阶后端。

**Verify:**

```powershell
Set-Location apps/web
npm ci
npm test
npm run build
Set-Location ../..
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_v01_golden_demo.py -q
.\.venv\Scripts\python.exe scripts/verify_compose_stack.py --golden-case --remove-demo-volume
```

**Review checkpoint:** 确认 Web 是业务扩展事件的参考渲染器，不把工单语义写进 core，也不把控制台宣传成客户业务系统。

**Commit:** `feat: add visual work order golden demo`

### Task A4：收敛 AI/Vibe Coding tools 开发入口

**Files:**

- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `docs/ai-instructions/00-project-overview.md`
- Modify: `docs/ai-instructions/02-domain-development.md`
- Modify: `docs/ai-instructions/03-common-tasks.md`
- Modify: `docs/ai-instructions/04-testing.md`
- Modify: `docs/ai-instructions/05-ai-coding.md`
- Modify: `docs/guide/04-first-plugin.md`
- Modify: `docs/add-a-domain.md`
- Modify: `README.md`
- Modify: `README.zh-CN.md`

**Steps:**

1. AGENTS/CLAUDE 默认读序加入黄金案例，但保持 MUST 简短且正文同步。
2. AI 手册把 `work_order_ops` 标为真实模式参考，把 `_scaffold` 标为最小新建起点；解释何时看哪个，避免整份复制黄金案例。
3. 提供中英文可复制配方：新增只读查询 tool、列表/图表/台账输出、需审批写 tool。
4. 每个配方要求 AI 先声明业务输入、权限、结构化返回、审批/幂等需求和测试，再修改代码。
5. 解释规范 JSON 错误与 SSE 信封由平台统一处理；domain 只产生业务结果/OutboundFragment，不直接控制 event_id/sequence。
6. 给出 tool list 过滤 + invoke 再鉴权、租户来自 RunContext、adapter 在 lifespan 注入的检查清单。
7. README 只保留一个短提示词，链接完整配方；避免首页变成内部开发手册。
8. `check_release_docs.py` 检查读序、MUST、黄金案例、三类配方、命令和中英文 README 链接。

**Verify:**

```powershell
.\.venv\Scripts\python.exe scripts/check_release_docs.py
bash scripts/check_ai_instructions.sh
$agents = Get-Content -Raw AGENTS.md
$claude = Get-Content -Raw CLAUDE.md
if ($agents -ne $claude) { throw 'AGENTS.md and CLAUDE.md differ' }
git diff --check
```

**Review checkpoint:** 用一段全新“新增设备巡检 tool”提示词走查，确认 AI 不需要阅读历史 superpowers 文件也能找到正确路径。

**Commit:** `docs: make tool development ai readable`

### Task A5：开源卫生、首页定稿、CI 与首发复核

**Files:**

- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `CHANGELOG.md`
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Modify: `.github/workflows/ci.yml`
- Create: `docs/assets/agentbridge-work-order-demo.png`
- Modify: `docs/assets/README.md`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/INDEX.md`
- Modify: `docs/releases/v0.1.0-tech-preview.md`
- Modify: `docs/release-validation/p3a-vibe-coding-release.md`
- Modify: `docs/superpowers/plans/README.md`

**Steps:**

1. CONTRIBUTING 聚焦 domain/tools 开发、MUST、测试、脱敏数据和 PR；SECURITY 提醒敏感内容不要进入公开 Issue；CHANGELOG 对齐 v0.1.0 实际能力与限制。
2. bug/PR 模板保持简短：复现步骤、影响、脱敏日志、测试结果、是否触及架构 MUST。
3. CI 保留 architecture、core/API、eval、SDK、Web 门禁；SDK/Web 统一 Node 22.14；增加轻量发布文档检查、Docker build 和黄金案例 smoke，不上传公共制品，也不引入独立发布流水线。
4. 用实际 Compose 黄金案例截取控制台截图，裁掉本机路径、token、DSN、用户信息和无关窗口；记录生成 commit 和复现步骤。
5. 把真实截图加入两份 README，删除内部占位注释；复核图片尺寸、alt text、语言切换、徽章与所有链接。
6. release notes 和验收记录说明：首页双语、Compose、黄金案例、AI 开发入口已通过；P2-B、生产稳定、多机仍未承诺。
7. 执行全量代码、文档、Node、Compose 门禁并审阅所有变更；不得因发布文档修改 core 架构边界。

**Verify:**

```powershell
$env:KNOWLEDGE_BACKEND='fake'
$python = Resolve-Path '.\.venv\Scripts\python.exe'
$env:Path = 'C:\nvm4w\nodejs;' + $env:Path
& $python -m pytest packages/core/tests apps/api/tests -q
& $python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
& $python scripts/import_scan_core.py
& $python scripts/import_scan_rag_engines.py
& $python scripts/run_evals.py
& $python -m ruff check packages/core/src apps/api scripts
& $python scripts/check_release_docs.py
bash scripts/check_ai_instructions.sh
Set-Location packages/sdk; npm ci; npm test; npm run build; Set-Location ../..
Set-Location apps/web; npm ci; npm test; npm run build; Set-Location ../..
docker compose config --quiet
& $python scripts/verify_compose_stack.py --golden-case --remove-demo-volume
git diff --check
git status --short
```

**Review checkpoint:** 分别以英文 GitHub 新访客、中文开发者、首次读仓 AI、现有业务集成者四个视角复核；所有首页声明都必须能由代码、文档或 smoke 证明。

**Commit:** `docs: complete v0.1 open source release readiness`

## 4. Spec 对齐矩阵

| Spec 要求 | 任务 | 证据 |
|-----------|------|------|
| 唯一权威路径、历史不误导 AI | A0 | release docs check |
| 中英文有吸引力的 GitHub 首页 | A1、A5 | release docs check、真实截图、人工文案复核 |
| 一套 Compose、零外部凭据 | A2 | compose config、stack smoke |
| 查询/图表/台账/审批黄金闭环 | A3 | Web tests、API test、golden smoke |
| AI 能按规则编写 tools | A4 | release docs check、三类提示词走查 |
| 基础开源卫生与 CI | A5 | governance docs、CI、全量门禁 |
| 技术预览边界诚实 | A0、A1、A5 | README、release plan、release notes |

## 5. 实施条件

开工前确认：

- [ ] 当前普通分支基于最新 `main`，没有 worktree；
- [ ] `.venv` 使用 Python 3.12；
- [ ] Node 22.14 可执行；
- [ ] Docker daemon 可用且允许构建/启动本项目专属 Compose 栈；
- [ ] 允许安装现有 lockfile/pyproject 声明的依赖；
- [ ] 允许提交每个任务的实现与测试。

Docker 暂不可用时可先完成 A0/A1/A4，但 A2/A3/A5 不得标记完成。

## 6. 完成定义

- [ ] A0–A5 全部实现、逐任务复核并提交。
- [ ] 英文和中文 README 均完整、吸引人、链接有效且声明真实。
- [ ] 一条 Compose 命令能启动整套零密钥体验。
- [ ] 控制台能演示脱敏工单列表、ECharts、台账草稿、审批与创建结果。
- [ ] AI 不读历史计划也能按 AGENTS/ai-instructions 编写安全 tools。
- [ ] 历史 spec/plan 已归档，不再显示虚假待实施状态或死链。
- [ ] 全量代码、Web/SDK、文档和 Compose 门禁通过。
- [ ] P2-B、多机和生产稳定仍明确延期。
- [ ] 不发布 PyPI/npm/GHCR，不创建正式 tag。

完成后，仓库达到 `v0.1.0` GitHub Release 候选状态；合并与正式 tag/release 另行确认。
