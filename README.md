# AgentBridge

**一句话：** 给你的业务系统加一层「能对话的 AI 接口」。流式输出、同一会话别抢跑这类公共事先由平台统一做；登录校验、权限、审计等能力平台也备好了，可按需打开。你的业务写成插件插进去。

**谁适合看这个仓库：** 要在自家服务器上接 AI 对话的后端 / 集成同学。  
**谁不适合：** 只想用现成聊天产品、不想自建服务的人。

---

## 用个例子理解

假设你有个内部业务系统，想让用户用自然语言问「这个单现在什么状态」。

- **你写：** 查单工具、对话怎么走（一个业务插件）
- **平台管：** 请求怎么流式返回、会话怎么管；权限与审计等能力备好了，可按需打开（例如没权限的工具不给模型看）

本仓库还带一个**调试网页**（AI 控制台），方便你本地试对话；客户真正用的业务界面要你们自己接 API。

---

## 约 5～10 分钟跑起来

需要：Python 3.12+。调试网页可选 Node 18+。

在仓库根目录：

**Windows（PowerShell）：**

```powershell
pip install -e "packages/core[dev]" -e "apps/api[dev]"
copy .env.example .env
cd apps\api
uvicorn main:app --reload --port 8000
```

**macOS / Linux：**

```bash
pip install -e "packages/core[dev]" -e "apps/api[dev]"
cp .env.example .env
cd apps/api
uvicorn main:app --reload --port 8000
```

另开一个终端起调试页（可选）：

```bash
cd apps/web && npm install && npm run dev
```

**怎样算成功（至少做到第一条）：**

1. 打开 <http://127.0.0.1:8000/health>，看到类似 `{"status":"ok"}`  
2. （推荐）用 curl / 冒烟脚本打 `echo`，或打开调试页 <http://127.0.0.1:5173> 选 `echo` 发「你好」，能收到回复  

依赖装好后，也可用根目录 `.\start-dev.ps1` / `./start-dev.sh` 起服务（脚本本身不负责安装依赖）。  
翻车排查与完整 curl 示例：[快速开始](docs/guide/02-quickstart.md)。

技术栈（了解即可）：Python 包 `agentbridge-core` / `agentbridge-api`；对话编排用 LangGraph，HTTP 用 FastAPI，流式用 SSE（一边生成一边推消息）。

---

## 你现在能用到什么

| 能力 | 人话 |
|------|------|
| 流式对话 | 客户端调 `POST /chat/stream`，服务边想边推事件 |
| 业务插件 | 放在 `apps/api/domains/`，请求里用 `route` 选中（如 `"route":"echo"`） |
| 权限 | 可选登录校验；工具可按角色隐藏或拒绝 |
| 知识检索 | 可接平台库或外部知识服务（改配置即可） |
| 调试台 | 看事件、插件、工具、提示词、用量等 |

---

## 仓库里都有啥

```text
packages/core/     # 核心库（编排与约定）
apps/api/          # HTTP 服务 + domains/ 业务插件
apps/web/          # 调试用 AI 控制台
packages/sdk/      # TypeScript 客户端
docs/              # 说明（新人先看 docs/guide/）
```

---

## 文档怎么读

1. **新人按顺序：** [为什么用](docs/guide/01-why.md) → [快速开始](docs/guide/02-quickstart.md) → [概念](docs/guide/03-concepts.md) → [第一个插件](docs/guide/04-first-plugin.md) → [控制台](docs/guide/05-console.md)
2. **总目录：** [docs/INDEX.md](docs/INDEX.md)
3. **正式产品约定：** [完整方案](docs/00-AgentBridge完整方案.md)
4. **给 AI 编程助手：** 见下一节；硬规则 [AGENTS.md](AGENTS.md)

---

## 用 AI 编程助手改这个仓库

本仓库按「人读 guide、助手读 AGENTS + ai-instructions」分开写了。  
**不绑某一家工具**：Cursor、Codex、Claude Code、其它能读本地仓库的助手都可以用同一套规则与提示词。

### 通用做法（任何工具）

1. 把**仓库根目录**当作项目根打开 / 作为工作目录（不要只挂子文件夹）。  
2. 新对话先让助手读硬规则，再给任务：
   - 必读：[`AGENTS.md`](AGENTS.md)
   - 细则：[`docs/ai-instructions/`](docs/ai-instructions/00-project-overview.md)（按任务看 00～04）
   - 可复制提示词与更多对话例：[docs/ai-instructions/05-ai-coding.md](docs/ai-instructions/05-ai-coding.md)
3. 若工具支持「项目说明 / 自定义指令」文件：把 `AGENTS.md` 全文或开场模板贴进去；有的工具也会读 `CLAUDE.md`（与 AGENTS **内容同步**）。

### 推荐开场（复制后改最后一句）

```text
你在改 AgentBridge。先读 AGENTS.md 的 MUST，再按任务读 docs/ai-instructions/
（00 概览 → 01 规则；加插件还要 02 与 docs/add-a-domain.md；命令 03；测试 04）。
遵守：不在 application/domains 里 new 适配器；domains 不握 EventSink 乱推；
核心库不写死业务名；适配器接线只在 apps/api/lifespan.py；
调用方不具备权限的工具不进 LLM 工具列表（调用时还会再鉴权）。
改完跑 pytest（core+api）、import-linter、
scripts/import_scan_core.py；知识相关测用 KNOWLEDGE_BACKEND=fake。
我的任务：<用你的插件名，例如 my_hello；这是新建任务名，不是仓库里现成的 route>
```

### 对话示例（短）

**加插件：**

> 按 `docs/ai-instructions/02-domain-development.md`，从 `_scaffold` 复制插件 `order_status`，先只回显查询文案，登记 `bootstrap.py`，不要改 `packages/core`，并告诉我怎样用 `route=order_status` 验收。

**只求命令、不改代码：**

> 按 `docs/ai-instructions/03-common-tasks.md`，我是 Windows，如何起 API 并用 `echo` 冒烟？给出命令和成功标准即可。

**查分层问题：**

> 按 `AGENTS.md` 与 `docs/ai-instructions/01-architecture-rules.md`，检查是否有 domain/application 直接创建适配器；有则改到 `lifespan` 注入，并跑 import-linter。

### 怎样算「AI 帮你改对了」

- 没违反 [`AGENTS.md`](AGENTS.md) 五条  
- 新插件：`POST /chat/stream` + 你的 `route` 能看到结束事件 `done`  
- 命令通过：见下文「开发自测」

### 各工具怎么接（可选）

| 工具 | 建议 |
|------|------|
| **任意 / Codex 等** | 每轮对话粘贴上面开场模板；或把 `AGENTS.md` 设为项目自定义指令 |
| **Claude Code 等** | 会读根目录 [`CLAUDE.md`](CLAUDE.md)（与 AGENTS 同步）；任务里仍可点名 `docs/ai-instructions/` |
| **Cursor** | 同上；另有可选 Skill [`.cursor/skills/agentbridge-dev/SKILL.md`](.cursor/skills/agentbridge-dev/SKILL.md)、规则摘要 [`.cursorrules`](.cursorrules)。**没有 Cursor 也不影响**，用开场模板即可 |

---

## 开发自测（简）

```bash
python -m pytest packages/core/tests apps/api/tests -q
python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
python scripts/import_scan_core.py
```

---

## 许可证与贡献

MIT，见 [LICENSE](LICENSE)。欢迎 Issue / PR；贡献规范文档稍后补。

---

## 现状（给决策者）

| | |
|--|--|
| 已经能用 | 流式对话、示例插件、权限骨架、单机运维、调试台、知识后端协议、AI 手册与**通用**提示词（可选 Cursor Skill） |
| 还在补 | 按需接入真实业务插件；贡献规范等外围文档 |
| 明确不做 | 云端 Studio、替代企业账号中心、默认无配置的多机集群 |
