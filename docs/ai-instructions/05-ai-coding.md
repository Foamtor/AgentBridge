# 用 AI 编程助手改本仓库（提示词与对话示例）

给**人**用：复制到任意能读本仓库的助手（Codex、Cursor、Claude Code、其它 IDE 助手等）。  
**不依赖某一家产品**；规则真源是 [`AGENTS.md`](../../AGENTS.md) 与本目录 `00`～`04`。

---

## 通用准备

1. 工作目录 / 工作区 = **仓库根目录**（才能稳定读到 `AGENTS.md`、`docs/`）。  
2. 新开对话时：先贴下面「开场模板」，或把 `AGENTS.md` 配进该工具的「项目指令 / 自定义说明」。  
3. `CLAUDE.md` 与 `AGENTS.md` 正文同步——只认 `CLAUDE.md` 的工具也能读到同一套 MUST。

### 各工具（可选便利，不是必须）

| 工具 | 额外便利 | 没有也能用 |
|------|----------|------------|
| Codex / 通用聊天式助手 | 每轮粘贴开场模板，或把 AGENTS 设为项目指令 | ✅ 只靠提示词 |
| Claude Code 等 | 自动读根目录 `CLAUDE.md` | ✅ 仍建议任务里点名 `docs/ai-instructions/` |
| Cursor | 可选 Skill `.cursor/skills/agentbridge-dev/SKILL.md`；摘要 `.cursorrules` | ✅ 不用 Skill，贴开场模板即可 |

---

## 开场模板（每次新对话建议先贴）

```text
你在改 AgentBridge 仓库。先读 AGENTS.md 的 MUST，再按任务读 docs/ai-instructions/：
- 概览 00，规则 01；加插件还要 02 + docs/add-a-domain.md；命令 03；测试 04。
不要违反：application/domains 不自己 new 适配器；domains 不握 EventSink 乱推；
核心库不写死业务名；适配器接线只在 apps/api/lifespan.py；
调用方不具备权限的工具不进 LLM 工具列表（列表过滤后，调用时仍须再鉴权）。
改完按范围验证：后端跑 pytest（core+api）+ import-linter + scripts/import_scan_core.py；
Web 跑 npm test + npm run build；仅文档按 04 做文档检查。
知识相关测试用 KNOWLEDGE_BACKEND=fake。
我的任务：<在这里写具体需求>
```

首发黄金案例：`apps/api/domains/work_order_ops/`。它是查询、图表、台账和审批的真实模式参考；新业务先从 `_scaffold` 开始，不能把 `work_order_ops` 的业务名或数据模型写入 core。

---

## 场景对话示例

### A. 加一个业务插件

**你可以说：**

```text
按 docs/ai-instructions/02-domain-development.md，新增业务插件 order_status：
- 复制 apps/api/domains/_scaffold 为 order_status
- 先做最小：用户问单号时回显「已收到查询：<query>」（可先不接真库）
- 登记 domains/bootstrap.py 与 DOMAIN_META_MAP
- 补一条 API 冒烟测试
- 不要改 packages/core
完成后给出：改了哪些文件、如何用 route=order_status 验收。
```

**助手应做到：** 只动 `domains/` + 总表注册；遵守 MUST；给出 `/chat/stream` 验收方式。

### B. 接外部知识检索

**你可以说：**

```text
按 docs/ai-instructions/03-common-tasks.md 的「接外部知识库」：
说明 .env 要怎么配 KNOWLEDGE_BACKEND=external 与 KB_EXTERNAL_BASE_URL；
指出业务插件应如何用 ctx.metadata["retriever"]，不要在 domain 里 new 客户端。
不要改我的业务逻辑，只改配置说明或必要时的 lifespan/工厂（若缺失再补）。
```

**助手应做到：** 接线仍在 lifespan；domain 只经注入使用 Retriever。

### C. 修分层违规

**你可以说：**

```text
检查 apps/api/domains/ 与 packages/core/src/agentbridge_core/application/：
是否有直接 import adapters 并创建实现的问题。若有，按 AGENTS.md 与
docs/ai-instructions/01-architecture-rules.md 改到 lifespan 注入。
改完跑 import-linter 与 import_scan_core.py。
```

### D. 只跑通本地 echo

**你可以说：**

```text
按 docs/ai-instructions/03-common-tasks.md，在本机起 API，用 echo 冒烟。
我是 Windows / macOS（选一个）。默认 AUTH_MODE=local 时走登录后的 /playground；
只有非生产隔离测试才允许 AUTH_MODE=disabled。不要改业务代码，只给命令与成功标准。
```

### E. 新增只读查询 tool

```text
为 <你的业务> 新增一个只读查询 tool。先读 AGENTS.md、02-domain-development.md，
从 _scaffold 起步；声明输入、required_permissions、结构化返回与 API 冒烟测试。
数据访问只使用 lifespan 注入的 DataSource/Port，不在 domain 创建 adapter；
无权限工具不可进入 LLM tools 列表，调用时仍须再鉴权。
```

### F. 新增列表、图表或台账输出

```text
参考 work_order_ops 的扩展事件模式，为 <你的业务> 输出列表、统计图表和/或台账预览。
事件使用 x.<你的业务>.* 与 OUTBOUND_EXTENSIONS_KEY；后端返回纯 JSON 数据，
前端不得执行事件中携带的脚本。不要把业务展示语义写进 packages/core。
```

### G. 新增需人工确认的写 tool

```text
为 <你的业务> 的写操作设计审批闭环：先定义版本化 payload、required permissions、
审批前预览、approval_id 幂等键、批准/拒绝后的结构化结果和测试。
批准后的 handler 返回 OutboundFragment；domain 不直接推 SSE，adapter 仍由 lifespan 组装。
```

---

## 使用注意

| 做法 | 原因 |
|------|------|
| 项目根 = 仓库根 | 稳定读到 `AGENTS.md`、`docs/` |
| 任务写清「只改 domain / 允许改 lifespan」 | 减少助手去改 core |
| 产品约定冲突时点名完整方案 | `docs/00-AgentBridge完整方案.md` |
| 默认认证先看 `AUTH_MODE` | `local` 是自托管默认；`disabled` 只限非生产隔离测试 |
| 不依赖 Cursor Skill 也能开发 | Skill 只是 Cursor 下的加速器 |

人类入门仍看 [docs/guide/](../guide/README.md)。
