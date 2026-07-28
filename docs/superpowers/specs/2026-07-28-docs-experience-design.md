# AgentBridge 文档体验设计（双入口）

> 状态：已确认（2026-07-28）；文风：白话、简明  
> 日期：2026-07-28  
> 受众：C — 人类集成方 + AI 编程助手，分两层  
> 实施顺序：**先 P1（GitHub 门面），再 P2（AI 可编程）**  
> 单次 Plan 范围：**仅 P1**（P2 另开 Plan，避免一个实施计划过大）

---

## 1. 目标

把 AgentBridge 从「内部工程仓」补成：

1. **GitHub 上像样的开源/产品仓**（人约 2 分钟看懂定位；按文档约 5～10 分钟跑通 `echo`）  
2. **面向 Cursor / Claude Code 等 AI 编程的可操作手册**（模型打开就知道禁区与改哪里）— **P2 交付**

业务插件大场景（`industry_qa` 等）不在本设计范围内；本设计只补**项目介绍与文档体验缺口**。

**权威优先级（写死，避免三套文档抢戏）：**

1. `docs/00-AgentBridge完整方案.md` — 产品约定冲突时以此为准  
2. `docs/guide/` + 根 `README.md` — 人类入门（P1）  
3. `AGENTS.md` + `docs/ai-instructions/` — AI 编程入口（P2）  
4. `docs/superpowers/` — 历史设计/实施记录，仅供追溯  

---

## 2. 非目标

- 不重写 `docs/00-AgentBridge完整方案.md` 全文（仍为权威深度约定）  
- 不清理 `docs/superpowers/` 历史稿（只加「归档」说明与导航降权）  
- 不做营销站 / 多语言站点  
- 不在本轮改代码结构或包名  
- **P1 不扩写** `AGENTS.md` / `ai-instructions`（只允许加「详见 P2 / 现有硬规则」一行链，避免半成品）  
- **不新增** `CONTRIBUTING.md`（P1 README 贡献节写：Issue / PR 欢迎；规范待补）  

---

## 3. 信息架构

```text
给人（P1）                         给 AI（P2）
─────────────                     ─────────────
README.md                         AGENTS.md / CLAUDE.md（保持同步，内容相同）
docs/guide/                       docs/ai-instructions/
  01-why.md                         00 … 04（扩写）
  02-quickstart.md                  反模式并入 01/02，不单开 05-do-not
  03-concepts.md
  04-first-plugin.md
  05-console.md
docs/INDEX.md                     （必做，非可选）

深度 / 归档（已有，只挂链）
docs/00-AgentBridge完整方案.md
docs/contracts.md / api-reference / architecture / deploy / …
docs/superpowers/   ← 标明历史设计；冲突以完整方案为准
```

**与现有长文的关系（防重复）：**

| 新文 | 职责 | 已有文如何用 |
|------|------|----------------|
| `guide/02-quickstart` | 最短跑通 | `deploy.md` 保留部署深度；README 只摘要 + 链到 guide/02 |
| `guide/04-first-plugin` | 第一天加插件故事 | 细节步骤仍以 `add-a-domain.md` 为准；guide 只写路径与验收 |
| `guide/03-concepts` | 术语一页 | 不替代 `architecture.md` / `contracts.md` |

**原则**

| 层 | 长度 | 语气 | 成功标准 |
|----|------|------|----------|
| README | 约 80～120 行正文（不含大段代码可略超） | 产品白话 | 陌生人知「是什么 / 怎么跑 / 去哪看」 |
| guide/* | 每篇一事；建议 ≤150 行 | 人话 + 术语一句解释 | 不用翻完整方案也能完成第一天 |
| AGENTS + ai-instructions | 清单、MUST、路径、命令 | 给模型执行 | 改插件/测通不踩硬规则 |

---

## 4. P1 — GitHub 门面（本轮先做）

### 4.1 README 重写结构

1. 一句话定位（无空徽章；有 CI 后再加真实 badge）  
2. 解决什么 / 不适合什么（保留并收紧）  
3. **跑起来**（可复制命令；PowerShell + bash 各一组；写明依赖：Python 3.12+、可选 Node 18+）  
4. 能力快览表（流式、插件、权限、知识后端、控制台）  
5. 仓库结构（极简树）  
6. 文档地图：默认 → `docs/guide/` 与 `docs/INDEX.md`；完整方案 / API 为深链  
7. 开发与验证：列 2～3 条命令；细节链到 `docs/ai-instructions/04-testing.md`（P2 前可暂链现有短文）  
8. License（现有 LICENSE）+ 贡献一句（见 §2，不建 CONTRIBUTING）

删除或下沉：过长术语表、与 guide 重复的「怎么用」长段。

### 4.2 新建 `docs/guide/`

| 文件 | 读者问题 | 内容要点 | 建议篇幅 |
|------|----------|----------|----------|
| `01-why.md` | 为什么用它？ | 痛点；三条线；边界（不做客户业务 UI / 不做云 Studio） | ≤80 行 |
| `02-quickstart.md` | 怎么跑？ | 安装、起 API/Web、`/health`、`echo` 冒烟；翻车：端口占用、`.env`、`KNOWLEDGE_BACKEND` | ≤120 行 |
| `03-concepts.md` | 这些词啥意思？ | domain、route、Port、SSE、适配器、租户；各一句 + 链到深度文 | ≤80 行 |
| `04-first-plugin.md` | 怎么加业务？ | 目标 → 复制 `_scaffold`/`echo` → `bootstrap` 注册 → 控制台选 route；**步骤细节链** `add-a-domain.md` | ≤100 行 |
| `05-console.md` | 控制台干嘛？ | 调试/插件/Tools/Prompt/用量/知识状态；明确「不是客户业务前端」 | ≤80 行 |

每篇文首加：上一篇 / 下一篇 / 回 INDEX。

### 4.3 导航修补

- **必做** `docs/INDEX.md`：三栏 — 人类入门 / AI 编程 / 深度与归档  
- `docs/superpowers/plans/README.md` 与 `docs/superpowers/specs/` 入口（若有）顶部加归档说明  
- 根 README「文档地图」以 guide 为默认路径  

### 4.4 P1 验收（可操作）

- [ ] 按 `guide/02` 能起 API，`GET /health` 返回 ok；`route=echo` 流式有事件（或执行 `scripts/smoke_echo.*`）  
- [ ] 未读完整方案，仅 README + guide，能说清项目定位与三条线  
- [ ] `docs/guide/*`、`docs/INDEX.md`、README 内链抽查无死链；无残留 `Agent-Base` / `agent_base_core` 作为现行包名  
- [ ] `guide/04` 明确指向 `add-a-domain.md`，不复制其全文  

---

## 5. P2 — AI 可编程（P1 完成后另开 Plan）

### 5.1 `AGENTS.md` / `CLAUDE.md`

- 两文件**内容保持一致**（改一处同步另一处；或 CLAUDE 只写「全文见 AGENTS.md」——**选定：内容一致双份**，兼容只读 CLAUDE 的工具）  
- 结构：一句话 → MUST 五条 → 默认读序 → 禁止项 → 验证命令  

### 5.2 扩写 `docs/ai-instructions/`

| 文件 | 扩写重点 |
|------|----------|
| `00-project-overview` | 目录地图、三条线、包名、权威优先级（同 §1） |
| `01-architecture-rules` | MUST/禁止 + 违反会怎样；`lifespan` 组装根；**反模式收此处** |
| `02-domain-development` | 加插件检查清单；**常见错误收此处** |
| `03-common-tasks` | 起服务、加 plugin、external RAG、跑测（可复制） |
| `04-testing` | 测什么、`KNOWLEDGE_BACKEND=fake`、命令 |

**不做** 单独的 `05-do-not.md`（并入 01/02，少一个入口）。

### 5.3 P2 验收

- [x] 只读 AGENTS + ai-instructions 00/01 能复述硬规则  
- [x] 按 02/03 能完成「echo 式新插件」注册与测试命令  
- [x] 与 P1 guide 交叉链接，术语与包名无矛盾  

> 实施记录：`docs/superpowers/plans/2026-07-28-docs-p2-ai.md`（2026-07-28）

### 5.4 P2 可读性与逻辑复审（2026-07-28）

| 维度 | 问题 | 修订 |
|------|------|------|
| 术语 | EventSink / application / 自托管未解释 | AGENTS / 01 补一句白话 |
| 受众 | 未标明「给编程助手」 | AGENTS / 00 加「你是谁」 |
| 权威 | guide 与 AGENTS 谁优先含糊 | 00 用表区分：产品→完整方案；写码禁令→AGENTS |
| 成功标准 | 02/04 缺「怎样算过」 | 02/04 补验收条 |
| 逻辑 | 「扩展事件必须 x.*」像每插件必发 | 改为「若发扩展事件则…」 |
| 路径 | checklist 写 `domains/echo` 易找错 | 统一 `apps/api/domains/...` |
| 命令 | 03 缺 Windows curl；与 P1 guide 不一致 | 补 PowerShell 示例 |
| 出站 | 「约定渠道」不可执行 | 写明 `OUTBOUND_EXTENSIONS_KEY` |
| 文档冲突 | knowledge-base 写 external 未实现，与代码/03 矛盾 | 改正 knowledge-base 配置表 |
| 分层 | domain 被说成像 application | 01 标明 domain≠application |

### 5.5 P2 逻辑复审第二轮（2026-07-28）

| 问题 | 修订 |
|------|------|
| MUST#4「只在 lifespan 创建」与 `apps/api/adapters/` 并存，易被理解成禁止该目录 | 区分「代码放置」vs「创建/接线点」；工厂可由 lifespan 调用 |
| MUST#1 后果写成「改业务代码」不准确 | 改为「改流程代码」；并写明 domain 也不要 import adapters |
| MUST#2 易误伤 `routes` 使用 `SseEventSink` | 标明禁止范围是 domain |
| MUST#5「没权限的工具」有歧义（无权限要求 vs 用户无权限） | 改为「调用方不具备权限的工具」 |
| 01 分层箭头像 application→adapters 的 import 链 | 改为「注入方向」说明 |
| 读序像必须 02 才能 04 | AGENTS/00：04 可单读 |
| 02 成功标准与「建议测试」打架 | 拆成最低成功 vs 强烈建议 |
| import-linter 能力边界未写 | 01 注明主要盯 application→adapters |
---

## 6. 文风与一致性

- **白话优先**：短句；少堆术语；必须用术语时，紧跟一句「是什么、这里干嘛用」  
- **简明**：能一张表说清就不用三段；guide 每篇一事，不写成说明书全集  
- 中文为主；代码 / 路径 / 命令保持英文  
- 产品名 **AgentBridge**；包名 **agentbridge_core** / **agentbridge-api** / **agentbridge-web**  
- 冲突时：完整方案 > guide/README > ai-instructions 摘要  
- 禁止：空洞套话（「本质上」「赋能」「一站式」）、未解释的英文缩写连打  

> 用户确认（2026-07-28）：设计 OK；文档要求白话、简明易懂。

---

## 7. 实施切片

| 切片 | 何时 | 内容 | 产出 |
|------|------|------|------|
| **P1-a** | 本轮 | README 重写 + `docs/INDEX.md` | 门面可看 |
| **P1-b** | 本轮 | `docs/guide/01`～`05` | 人类第一天路径 |
| **P1-c** | 本轮 | superpowers 归档说明 + 死链检查 | 导航不翻车 |
| **P2-a / P2-b** | **P1 合并后再开** | AGENTS + ai-instructions | AI 任务手册 |

批准后：对 **P1-a～c** 写 writing-plans → 实现；P2 不写入同一 Plan 的「完成定义」。

---

## 8. 明确不做（防范围膨胀）

- 英文版、视频、自动 API 站点  
- 验证分支业务插件文档并进主线门面  
- P1 阶段大改 `ai-instructions` 正文  
- 新建 CONTRIBUTING / CI badge 造假  

---

## 9. 自审记录（2026-07-28）

| 问题 | 处理 |
|------|------|
| 「可选」INDEX / 05-do-not / CONTRIBUTING 含糊 | INDEX 改为必做；05-do-not 取消；CONTRIBUTING 明确不做 |
| P1+P2 塞进一个 Plan 过大 | 写明单次 Plan 仅 P1 |
| README「徽章占位」易做成空壳 | 改为有 CI 再加 |
| guide 与 `add-a-domain` / `deploy` 职责重叠 | §3 增加对照表 |
| 「5 分钟」不可验证 | 改为约 5～10 分钟 + 可操作验收项 |
| AGENTS vs CLAUDE 是否同步 | 选定双份内容一致 |

---

## 10. 人类可读性复审（2026-07-28 晚）

从「陌生人打开 GitHub」角度复审后修订 P1 门面（README + guide + INDEX）。主要结论：

| 维度 | 问题 | 修订 |
|------|------|------|
| 30 秒定位 | 「自托管底座」偏行话，缺场景 | README / 01 用具体对话例子开场；标明谁适合/不适合 |
| 成功标准 | 只写命令，不写「成功长什么样」 | README / 02 / 04 / 05 补可见验收 |
| 术语负担 | IAM/OIDC、thread_id、graph 未解释 | 01 用白话括注；03 补词条 |
| 路径感 | INDEX 只列文件名 | 改成「读完会知道 / 什么时候打开」 |
| 内部气味 | README「P2」对陌生人无意义 | 改为「还在补…」对外表述 |
| 可复制性 | 接口示例不可直接 curl | 02 补 Windows/Unix curl |

## 11. 逻辑复审（2026-07-28）

| 问题 | 处理 |
|------|------|
| 「平台统一做登录/权限」像开箱必开，与默认 `AUTH_REQUIRED=false`、按需打开矛盾 | README 一句话改为：公共流式/互斥默认有；登录权限审计可按需开 |
| `apps/api` 既是底座又含 `domains/`，三块表易误解 | 01 标明插件挂在 domains，勿把整个 api 当业务 |
| 成功标准把可选调试页写成必过 | README 改为「至少 health；推荐再打 echo」 |
| `start-dev` 像能替代安装 | 标明脚本不起装依赖 / 不复制 .env |
| guide 顺序第 5 篇才讲控制台，但第 2 篇已用 | 目录与 05 注明「复习边界」，非第一次才打开 |
| 「半天跑通+加插件」易过度承诺 | INDEX 拆成：第 2 篇跑通；加插件另计时间 |
| 04 与 `add-a-domain`：先抄 echo 还是 `_scaffold` | 04 改为先读 echo、动手优先 `_scaffold` |
| 事件口头「开始/文本/结束」与契约类型名不完全对应 | 改用 `start` / `text_delta` / `done` |
| AGENTS 五条 vs guide「三条」 | 03 改为入门四条并链完整五条 |