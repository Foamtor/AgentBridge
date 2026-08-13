# AgentBridge

给业务系统接一层 AI 对话能力（软件装在你自己的机器/机房上，叫**自托管**）：  
业务做成插件；流式输出、同一会话别抢跑等由平台统一做。登录校验、权限、审计等能力平台也备好了，可按需打开。

**v1.0.0 的首发用法：** clone/fork 后让 AI 先读本文件与 `docs/ai-instructions/`，参考 `apps/api/domains/work_order_ops/`，按规则编写自己的 domain/tools/tests，再用根目录 Compose 验证。`work_order_ops` 是真实业务模式参考，不是要复制进 core 的默认业务。

本文件与 `CLAUDE.md` **正文同步**（改一处请改另一处）。

**你是谁：** 改本仓库的编程助手 / 集成开发者。先守住下面 MUST，再动代码。

## MUST（必须遵守）

1. **核心库流程层（`agentbridge_core.application`）禁止直接 import `adapters`（适配器实现）**  
   违反：流程层绑死具体实现，换数据库/检索时要改流程代码。  
   （业务插件 `domains/` 同样不要 import `agentbridge_core.adapters` 抄近路，见手册 01。）

2. **业务插件（`domains/`）不要自己拿着 `EventSink`（事件发送口）乱推事件**  
   禁止的是 **domain**；HTTP 路由 / 生命周期把 sink 交给平台推送，这是正常组装。  
   违反：SSE（流式推送）顺序/编号/落库与平台不一致。

3. **核心库 `packages/core` 的源码里不能写死某个业务插件名字**  
   违反：核心库绑死业务，无法多插件共用。

4. **适配器的「创建并接到应用上」只放在组装根**  
   生产路径：`apps/api/lifespan.py`（及其调用的工厂）。  
   适配器**代码**可在 `packages/core/.../adapters` 或 `apps/api/adapters`。  
   **测试**可在 `conftest` / 测例里注入假适配器（这不算违规）。  
   不要在 `application` 或 `domains/` 里 `new` 适配器。  
   违反：测试难注入，配置与实现散落。

5. **调用方不具备权限的工具，不能进入模型可见的工具列表**  
   且调用时仍须再鉴权一次（列表过滤 + `invoke_tool` 再 `decide`，见完整方案）。  
   违反：模型可能看见或调用不该用的工具。

完整方案另有（能力打开后强制，见 `docs/00-AgentBridge完整方案.md` §10.1）：  
跨租户在 Port 层失败；默认走 Gateway 时模型调用必须经 Gateway。

## 默认读序（改代码前）

1. 本文 MUST  
2. `docs/ai-instructions/00-project-overview.md` → `01-architecture-rules.md`  
3. 加/改插件才读：`02-domain-development.md`  
4. 要命令：`03-common-tasks.md`；要跑测：`04-testing.md`（可按需单读，不必先读完 02）  
5. 需要场景感：`docs/guide/`；**人要复制提示词**：`docs/ai-instructions/05-ai-coding.md`  
6. 产品约定冲突：以完整方案为准，并回头改 AGENTS / 手册使之一致

## 禁止速查

| 不要 | 要 |
|------|-----|
| `application` / `domains` 里 `import` 适配器类并自己创建 | 依赖 Port 或已注入对象；创建/接线只在组装根（测例可注入） |
| 在 domain 里直接发 SSE / 握着 `EventSink` | 扩展事件写入 `OUTBOUND_EXTENSIONS_KEY`（`agentbridge_core.protocol.fragments`），由生命周期统一推 |
| 在 `packages/core` 写 `echo` / 某客户插件名 | 插件只放 `apps/api/domains/` |
| 把当前调用方用不了的工具仍塞进 LLM tools 列表 | 权限过滤后再暴露给模型；调用时再 `decide` |
| 为「方便」改核心去迁就一个业务 | 先加/改 domain；确需改核心则按完整方案评审 |

## 验证命令（改完至少跑）

```bash
python -m pytest packages/core/tests apps/api/tests -q
python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
python scripts/import_scan_core.py
```

知识相关自测：优先 `KNOWLEDGE_BACKEND=fake`（避免本机 `.env` 指到 `external` / `langchain_pg` 把平台测搞怪）。

细则：`docs/ai-instructions/`。人类门面：`README.md`、`docs/guide/`。

## Design Context

### Users

The primary user is an open-source developer who has just cloned AgentBridge and wants to verify that the platform works before investing in an integration. Their first job is to run the bundled `work_order_ops` flow, understand what the platform handled, and inspect enough technical evidence to trust the result. After that, the same surface should help them test their own plugin without pretending to be a customer-facing business application.

### Brand Personality

Restrained, trustworthy, precise. The interface should feel like a dependable developer instrument: calm under repeated use, explicit about state and boundaries, and honest about what is demo data versus platform behavior.

### Aesthetic Direction

Light-first, utilitarian, and editorially structured. Use quiet neutral surfaces, strong typographic hierarchy, compact controls, and a small number of semantic status colors. Avoid marketing-page composition, decorative gradients, card-heavy dashboards, playful AI imagery, glass effects, oversized headings, and dark neon "AI console" styling.

### Design Principles

1. Prove value in the first three minutes: make the golden validation path the obvious first action.
2. Separate platform evidence from business output: results, approval state, and protocol events should be distinct but connected.
3. Reveal complexity progressively: keep tokens, thread IDs, raw events, and admin controls available without making them the first screen.
4. Make every state explicit: connection, running, waiting for approval, succeeded, failed, and cancelled must be unambiguous without relying on color alone.
5. Treat bilingual support as a product capability: one global language choice, complete translations, and no mixed-language primary workflows.
6. Stay truthful to the open-source scope: label synthetic data, offline model behavior, optional production capabilities, and the debug console's non-customer-facing role.
