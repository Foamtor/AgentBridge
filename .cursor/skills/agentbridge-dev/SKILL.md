---
name: agentbridge-dev
description: >-
  Develops AgentBridge (agentbridge_core / apps/api domains) while enforcing
  architecture MUST rules: no application→adapters imports, domains must not
  own EventSink, adapters wired only in lifespan, no domain names in core,
  unauthorized tools out of LLM tool lists. Use when editing this repo in
  Cursor, adding a domain/plugin/route, changing lifespan or adapters, or when
  the user mentions AgentBridge, domains/, echo, chat/stream, or AGENTS.md.
  (Non-Cursor tools should follow AGENTS.md + docs/ai-instructions/05-ai-coding.md
  prompts instead of this skill.)
---

# AgentBridge 开发

## 先做

1. 读仓库根目录 `AGENTS.md`（与 `CLAUDE.md` 同步）五条 MUST。  
2. 按任务打开手册（勿把 `docs/superpowers/` 当现行规格）：
   - 地图 / 权威：`docs/ai-instructions/00-project-overview.md`
   - 分层 / 反模式：`01-architecture-rules.md`
   - 加插件：`02-domain-development.md` + `docs/add-a-domain.md`
   - 命令：`03-common-tasks.md`
   - 测试：`04-testing.md`
3. 产品约定冲突：以 `docs/00-AgentBridge完整方案.md` 为准，并回修 AGENTS/手册。

## 改哪里

| 意图 | 动哪里 | 别动 |
|------|--------|------|
| 新业务对话能力 | `apps/api/domains/<name>/` + `domains/bootstrap.py` | `packages/core` 写死业务名 |
| 换 DB/检索/锁实现 | `apps/api/lifespan.py` + `apps/api/adapters/` 或 core adapters | `application` / domain 里 `new` 适配器 |
| HTTP 入参/状态码 | `apps/api/routes/` | 在路由里写业务编排 |

## 加插件最短路径

1. 读 `apps/api/domains/echo/`；复制 `_scaffold` → `domains/<name>/`  
2. 登记 `apps/api/domains/bootstrap.py`（`register` + `DOMAIN_META_MAP`）  
3. 扩展事件（若有）：`OUTBOUND_EXTENSIONS_KEY`，`type` = `x.<name>.*`  
4. 冒烟：`POST /chat/stream`，`route=<name>`，见 `done`  
5. 建议补测：参考 `apps/api/tests/test_chat_stream.py`

## 验证（改代码后）

```bash
python -m pytest packages/core/tests apps/api/tests -q
python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
python scripts/import_scan_core.py
```

知识相关自测：优先 `KNOWLEDGE_BACKEND=fake`。

## 文风

对人说明用白话；路径/命令英文。不发明与 AGENTS 冲突的新硬规则。
