# 测试

## 改完怎样算过关（最低）

| 你改了什么 | 最低要过 |
|------------|----------|
| 任意代码 | 相关 pytest + `import-linter` + `import_scan_core.py`（见下方命令） |
| 新/改 domain | 上表 + 新 `route` 能 `done`（测试或手工 `/chat/stream`） |
| 仅文档 | 不强制 pytest；改了 `ai-instructions` 文件名时跑存在性检查 |

「相关 pytest」= 至少覆盖你改动的包；不确定就跑核心+API 全量。

## 测什么

| 范围 | 建议 |
|------|------|
| 核心库 | `packages/core/tests` — 不依赖真实大模型 |
| API | `apps/api/tests` — 默认假运行时，见下 |
| Web | `apps/web` — Vitest + TypeScript/Vite 生产构建 |
| 分层 | import-linter + `scripts/import_scan_core.py` |
| 本手册文件是否还在 | `bash scripts/check_ai_instructions.sh`（Git Bash / WSL；只检查文件存在） |

## 环境变量坑（先看这里）

| 变量 | 本地/CI 建议 | 说明 |
|------|----------------|------|
| `AGENTBRIDGE_FAKE_RUNTIME` | 测 API 时多为 `1`（`apps/api/tests/conftest.py` 会设） | `1` = 假 GraphRuntime；个别真跑 echo 图的用例会设 `0` |
| `KNOWLEDGE_BACKEND` | 平台自测用 `fake` | 本机 `.env` 若是 `external` / `langchain_pg`，可能拖垮或改变知识相关测——测前改回或卸掉 |
| `AUTH_MODE` | 正常自托管用 `local`；测试 fixture 可用 `disabled` | `disabled` 只限非生产隔离测试；生产环境禁止关闭认证 |
| `AUTH_REQUIRED` | 不作为新配置的主开关 | 仅保留给旧 OIDC 配置迁移；新配置优先使用 `AUTH_MODE` |

说人话：你电脑上的 `.env` 会进进程；跑测前确认别指着外部 RAG 还以为在测假后端。

## 常用命令

在仓库**根目录**：

```bash
python -m pytest packages/core/tests apps/api/tests -q
python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
python scripts/import_scan_core.py
```

只要核心 / 只要 API：

```bash
python -m pytest packages/core/tests -q
python -m pytest apps/api/tests -q
```

Web 改动：

```bash
cd apps/web
npm test
npm run build
```

可选：`python scripts/run_evals.py`（任务明确要求评测再跑）。

## 新插件最少测什么

- 一条带合法认证上下文的 `/chat/stream`，`route` = 你的名字；或登录后在 `/playground?route=<名字>` 验证
- 断言风格对齐现有用例：通常包含 `start`、业务相关内容、`done`  
- 参考：`apps/api/tests/test_chat_stream.py` 里 real echo 用例  

## 相关

- 硬规则：[AGENTS.md](../../AGENTS.md)  
- 任务命令：[03-common-tasks.md](./03-common-tasks.md)
