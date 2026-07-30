# P0 发布基线与对外口径 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 冻结 `v0.1.0` 技术预览的发布口径，使正式方案、路线图、部署说明和首版 release notes 对能力状态与支持边界给出一致表述。

**Architecture:** 保留既有 M0–M10 能力标签；M11/M12 为“实现已合入、尚待发布验收”。`v0.1.0` 是当前技术预览，不重定义既有 `v1.0` 和 `v2.0` 的能力语义。P1 工单案例与 P2 真实环境验证是稳定发布条件，不在本计划实现功能。

**Tech Stack:** Markdown、GitHub Actions、Python 3.12+、PostgreSQL/pgvector、Redis、OIDC、LLM Gateway。

## Global Constraints

- `docs/00-AgentBridge完整方案.md` 是产品与架构权威说明；其它门面文档必须与其一致。
- M11/M12 的“已实现”只表示已合入代码和现有测试，不得表述为生产验收完成。
- 单机主承诺仍是 M0–M4；多机仅在显式配置 Redis 锁和限流后可验证。
- `external` 知识后端可只检索；不支持摄取时 `/ingest` 返回 501。
- 本计划不改包版本、发布包、镜像或业务代码。

---

## 文件结构

- Modify: `docs/00-AgentBridge完整方案.md` — 正式版本语义、M11/M12 和 P0/P1 发布状态。
- Modify: `docs/roadmap.md` — 用户可读的当前状态、技术预览与稳定版条件。
- Modify: `docs/release-plan.md` — 发布阶段、技术预览与正式稳定版门槛的唯一衔接说明。
- Modify: `README.md` — 对外定位和技术预览边界。
- Modify: `docs/deploy.md` — 支持矩阵、真实部署前提和明确限制。
- Create: `docs/releases/v0.1.0-tech-preview.md` — 首版预览 release notes。
- Modify: `docs/INDEX.md` — release notes 入口。

### Task 1: 统一正式方案、路线图与版本语义

**Files:**
- Modify: `docs/00-AgentBridge完整方案.md:1-10, 460-484, 附录 D`
- Modify: `docs/roadmap.md:1-84`
- Modify: `docs/release-plan.md:118-139`
- Test: 文本一致性检查

**Consumes:** 现有 M0–M12 状态和 `docs/release-plan.md` 的 P0–P3 分期。

**Produces:** `v0.1.0` 技术预览；`v1.0` 保持 M0–M4 单机稳定能力标签；M11/M12 在发布验收完成前为 🟡。

- [ ] **Step 1: 写出会失败的文档一致性断言**

```powershell
$spec = Get-Content -Raw docs/00-AgentBridge完整方案.md
$roadmap = Get-Content -Raw docs/roadmap.md
$releasePlan = Get-Content -Raw docs/release-plan.md
if ($spec -notmatch 'v0\.1\.0' -or $spec -notmatch 'M11' -or $roadmap -notmatch '技术预览' -or $releasePlan -notmatch 'v0\.1\.0' -or $releasePlan -notmatch 'P0–P3') { throw 'release baseline wording is not aligned' }
```

- [ ] **Step 2: 运行断言并确认失败**

Run: Step 1 的 PowerShell 命令。

Expected: `release baseline wording is not aligned`。

- [ ] **Step 3: 修改权威方案与路线图**

在完整方案中新增 M11“多知识后端”和 M12“AI 控制台”，状态写为“实现已合入，待发布验收”；在版本表增加：

```markdown
| v0.1.0 | 技术预览：现有能力可体验；P1 参考案例与 P2 生产验证尚未完成，不承诺生产稳定或默认多机 |
| v2.1 | M11 + M12 发布验收通过；版本是否发布取决于 P1/P2，而非仅代码合入 |
```

保留既有 `v1.0 = M0–M4` 和 `v2.0 = M10`。在 `release-plan.md` 明确：`v0.1.0` 是 P0 后可形成的技术预览说明，`v1.0.0` 仍须 P0–P3、黄金案例、真实生产路径、全套 CI 和公开漏洞报告渠道；路线图链接该门槛，避免把“代码合入”写成“发布完成”。

- [ ] **Step 4: 重新运行一致性断言**

Run: Step 1 的 PowerShell 命令。

Expected: 无输出、退出码 0。

- [ ] **Step 5: 审阅改动范围**

Run: `git diff --check; git diff -- docs/00-AgentBridge完整方案.md docs/roadmap.md docs/release-plan.md`

Expected: 无空白错误；仅版本、状态与链接发生变化。

- [ ] **Step 6: 提交**

Run: `git add docs/00-AgentBridge完整方案.md docs/roadmap.md docs/release-plan.md; git commit -m "docs: align release baseline and milestones"`

### Task 2: 写入支持矩阵和已知限制

**Files:**
- Modify: `docs/deploy.md:1-110`
- Modify: `README.md:现状（给决策者）`
- Test: 支持矩阵内容检查

**Consumes:** `Settings` 的 `KNOWLEDGE_BACKEND`、`LOCK_BACKEND`、`RATE_LIMIT_BACKEND`、OIDC 和 Gateway 配置。

**Produces:** 用户能判断一个环境是本地体验、单机技术预览、单机生产验收候选，还是尚未承诺的多机组合。

- [ ] **Step 1: 写出会失败的支持矩阵断言**

```powershell
$deploy = Get-Content -Raw docs/deploy.md
foreach ($word in @('技术预览', 'langchain_pg', 'external', 'Redis', 'OIDC', '不支持摄取')) { if ($deploy -notmatch [regex]::Escape($word)) { throw "missing support-matrix term: $word" } }
```

- [ ] **Step 2: 运行断言并确认失败**

Run: Step 1 的 PowerShell 命令。

Expected: 至少缺少 `技术预览` 或 `不支持摄取`。

- [ ] **Step 3: 增加支持矩阵**

在 `docs/deploy.md` 的部署方式后新增表格，包含“本地体验、单机技术预览、单机生产验收候选、双实例验证”四行；列出 Postgres、pgvector、Redis、OIDC、Gateway、RAG 后端和承诺级别。增加以下准确边界：

```markdown
- `fake` 仅本地/CI，不能作为生产证据。
- `langchain_pg` 需要 pgvector、`[rag]` extra 和兼容 embedding 服务。
- `external` 支持检索；后端未实现 ingest 时 `POST /ingest` 返回 501。
- 多实例必须设置 Redis 锁和限流；未演练前仅技术预览。
```

将 README 的“已经能用”改为“已有实现”，并链接支持矩阵和发布规划。

- [ ] **Step 4: 运行支持矩阵断言**

Run: Step 1 的 PowerShell 命令。

Expected: 无输出、退出码 0。

- [ ] **Step 5: 检查相对链接**

Run: `rg -n "release-plan|roadmap|deploy" README.md docs/INDEX.md docs/deploy.md`

Expected: README、INDEX、deploy 可相互到达，不出现旧项目名或死链。

- [ ] **Step 6: 提交**

Run: `git add README.md docs/deploy.md; git commit -m "docs: add preview support matrix"`

### Task 3: 建立技术预览 release notes 入口

**Files:**
- Create: `docs/releases/v0.1.0-tech-preview.md`
- Modify: `docs/INDEX.md:深度与归档`
- Test: release notes 完整性检查

**Consumes:** Task 1 的版本定义和 Task 2 的支持矩阵。

**Produces:** 一份可供 tag/release 复用且不夸大承诺的首版说明。

- [ ] **Step 1: 写出会失败的 release notes 检查**

```powershell
$path = 'docs/releases/v0.1.0-tech-preview.md'
if (-not (Test-Path $path)) { throw 'release notes missing' }
```

- [ ] **Step 2: 运行检查并确认失败**

Run: Step 1 的 PowerShell 命令。

Expected: `release notes missing`。

- [ ] **Step 3: 创建 release notes**

文件必须包含：

```markdown
# v0.1.0 技术预览
## 可体验：流式对话、domain 插件、权限双检、审计/回放、RAG 接入、调试控制台
## 推荐环境：Python 3.12、Postgres；RAG 另需 pgvector 与 embedding 服务
## 已知限制：P1 工单黄金案例尚未交付；真实生产验证未完成；多机非默认；external ingest 可返回 501
## 升级与反馈：配置变更前备份；一般问题走 Issue；公开 tag/release 前必须先发布 SECURITY.md 中的私密漏洞报告渠道
```

在 `docs/INDEX.md` 增加链接。若 P3 尚未提供并验证私密漏洞报告渠道，本文件只可作为仓库内技术预览草案，不得据此创建公开 tag 或 GitHub Release；不得虚构邮箱、Issue 模板或平台功能作为报告渠道。

- [ ] **Step 4: 运行 release notes 检查和格式检查**

```powershell
$text = Get-Content -Raw docs/releases/v0.1.0-tech-preview.md
foreach ($heading in @('可体验','推荐环境','已知限制','升级与反馈')) { if ($text -notmatch $heading) { throw "missing heading: $heading" } }
git diff --check
```

Expected: 无输出、退出码 0。

- [ ] **Step 5: 提交**

Run: `git add docs/releases/v0.1.0-tech-preview.md docs/INDEX.md; git commit -m "docs: add v0.1.0 technical preview notes"`

## 全量验证

- [ ] **Step 1: 检查文档状态与空白错误**

Run: `git diff --check HEAD~3..HEAD; rg -n "v0\.1\.0|M11|M12|技术预览|P0–P3|SECURITY\.md" README.md docs/00-AgentBridge完整方案.md docs/roadmap.md docs/release-plan.md docs/deploy.md docs/releases/v0.1.0-tech-preview.md`

Expected: 无空白错误；所有门面文档包含相同技术预览口径。
