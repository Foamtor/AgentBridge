# P2-A 运行、安全、RAG 与控制台发布验证 Implementation Plan

> **状态：** 已完成（2026-08-01）；P2-B 的生产部署、多机与恢复验证仍延期。当前首发范围以 [v0.1.0 Plan](./2026-08-01-p3a-open-source-release-preparation.md) 为准。

**Goal:** 在暂不开展全新环境部署、迁移升级/回滚、备份恢复和双实例演练的前提下，完成认证、授权、RAG 后端、运行故障和 AI 控制台的可重复验证，并形成可公开的脱敏证据。

**Architecture:** 验证只通过公开 HTTP/SSE、既有 ports、lifespan 组装后的应用和可控协议服务观察行为。测试不得绕过 middleware 注入 claims，不得直接修改 domain 状态，不得为测试破坏 Port/Adapter 分层。真实 RAG-Agent 始终只读；写入型 RAG/审批测试仅使用 AgentBridge 专用测试库。

**Tech Stack:** Python 3.12+、FastAPI/TestClient、pytest/pytest-asyncio、python-jose、httpx MockTransport、PostgreSQL/pgvector、TEI、Node 22.14、Vite、Vitest、React Testing Library、GitHub Actions。

## 1. 发布边界

明确延期到 **P2-B**：

- 空白主机或干净容器部署；
- 数据库迁移、升级/回滚、备份恢复；
- Authentik 等具体 IdP 的现场 client/redirect 配置与登录握手；
- 两 API 实例互斥、Redis 分布式锁和跨实例限流；
- 指定厂商 external RAG 服务的现场部署与认证联调。

P2-A 完成后仍只能维持技术预览口径，不能声称 `v1.0.0` 单机稳定、特定 IdP 已认证或多机已验证。

## 2. 固定验证方式

### 身份

- 必测 HS256：通过 `AUTH_REQUIRED=true`、`AUTH_DEV_STUB=false` 和 `OIDC_JWT_SECRET` 走真实 HTTP middleware。
- 必测 OIDC/JWKS：测试进程启动受控 discovery/JWKS 服务，使用临时 RSA key，验证 issuer、audience、kid、签名和过期时间。
- 受控 JWKS 服务是协议契约测试，不代表 Authentik 现场验收；不得修改现有 Authentik 配置。

### RAG

- `langchain_pg`：使用可销毁的 AgentBridge 专用 PostgreSQL/pgvector 测试库和当前 TEI 服务，允许写入脱敏测试文档。
- `rag_agent_pg`：复用 `scripts/verify_rag_agent_readonly.py`，固定租户 `rag-agent-demo`，只读现有 RAG-Agent 数据。
- `external`：使用现有 `ExternalRagRetriever` + `httpx.MockTransport` 做完整 HTTP 契约与失败策略测试；这不是 `KNOWLEDGE_BACKEND=fake`，但也不宣称完成具体厂商现场联调。

### 控制台

- 前端单元/交互测试固定为 Vitest + React Testing Library + jsdom。
- P2-A 验证 `npm ci`、`npm test`、`npm run build`，以及前端权限表现与 API 权限一致性。
- Playwright/真实浏览器部署验收延期到 P2-B；P2-A 的调试→回放→审计闭环由 API HTTP/SSE 验收脚本证明。

## 3. 全局约束

- 不提交或输出 DSN、密码、JWT 原文、私钥、嵌入向量、业务正文或完整模型输出。
- 跨租户、无权限、审批超时和依赖失败必须断言零副作用，不能只检查 HTTP 状态码。
- 不修改 RAG-Agent 源码、配置、schema 或数据；`rag_agent_pg` 只使用 read-only transaction。
- 写入型 pgvector/审批测试不得复用或清理 RAG-Agent 数据库。
- `application` 不 import adapters；domain 不持有 `EventSink`、不创建 adapter；core 不出现业务插件名；工具保持列表过滤与调用期复检。
- TDD：先新增失败测试并确认 RED，再写最小实现；每个任务独立提交、审阅、修复后才进入后继任务。
- Fake/Memory 可以跑回归门禁，但不得替代本计划明确要求的 PostgreSQL、pgvector、TEI 和 JWKS 证据。

## 4. 任务与依赖

| 任务 | 内容 | 依赖 |
|---|---|---|
| A0 | 执行前基线与隔离 | 无 |
| A1 | 验收契约与脱敏证据框架 | A0 |
| A2 | JWT/OIDC middleware 验证 | A1 |
| A3 | 授权、租户隔离与审计脱敏 | A2 |
| A4 | pgvector 与只读 RAG-Agent | A1 |
| A5 | external RAG HTTP 契约与失败策略 | A1 |
| A6 | 取消、EventLog 与审批投递幂等 | A1 |
| A7 | 限流与依赖健康语义 | A1 |
| A8 | 控制台测试工具链、权限表现与闭环 | A2、A3 |
| A9 | 全量复核与发布口径 | A3–A8 |

```text
A0 → A1 ─┬→ A2 → A3 ─→ A8 ─┐
         ├→ A4 ──────────────┤
         ├→ A5 ──────────────┤→ A9
         ├→ A6 ──────────────┤
         └→ A7 ──────────────┘
```

## 5. 独立实施任务

### Task A0：建立隔离执行环境并记录基线

**Files:** 不修改生产文件。

**Steps:**

1. 确认本计划和索引已纳入待实施分支；从最新 `master` 创建并切换到 `codex/p2a-release-validation` 分支，禁止直接在主分支实施，也不创建 worktree。
2. 确认除计划文件外没有未知用户改动；若有重叠改动，停止并报告。
3. 准备隔离开发环境并核对运行时：

```powershell
python -c "import sys; assert sys.version_info >= (3, 12), sys.version"
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e "packages/core[dev,postgres,rag]" -e "apps/api[dev,datasource,rag]"
node --version
npm --version
```

Node 主验证版本为 22.14；其它版本只能用于辅助检查，不能替代 CI 的 Node 22.14 证据。若 `node`/`npm` 不存在，A8 标记 blocked，先补本机工具链或在受控 CI 中执行，不能跳过 Web 门禁。

4. 在不注入真实凭证的环境运行基线：

```powershell
$env:KNOWLEDGE_BACKEND='fake'
python -m pytest packages/core/tests apps/api/tests -q
python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
python scripts/import_scan_core.py
python scripts/import_scan_rag_engines.py
Push-Location apps/web; npm ci; npm run build; Pop-Location
```

5. 运行一次全仓 `ruff check packages/core/src apps/api scripts` 并将既有问题数记录为基线；P2-A 不批量格式化未触及文件。每个 P2-A 提交必须对其新增/修改的 Python 路径运行 Ruff 并保持零错误；全仓 Ruff 清零移交 P3 发布工程。
6. 在验收记录中保存提交 SHA、Python/Node/npm 版本、测试通过/跳过数量、既有警告和 Ruff 债务数；不得把 skip 写成 pass。

**Run:** 本任务依次运行上述环境准备和基线命令；任一命令失败即停止，不进入 A1。

**Expected:** 现有 Python/架构门禁和 Web build 通过；真实 PostgreSQL/RAG 测试可以在 A4 前明确标为未运行。

**Commit:** 无；A0 是执行前门禁。

### Task A1：冻结验收契约与脱敏证据框架

**Files:**

- Create: `docs/release-validation/p2a-runtime-security-rag-console.md`
- Modify: `docs/release-plan.md`
- Modify: `docs/roadmap.md`
- Create: `scripts/check_p2a_evidence.py`
- Test: `apps/api/tests/test_p2a_evidence_contract.py`

**Steps:**

1. 先写失败测试，要求验收记录包含 A0–A9、P2-B 延期项、环境版本、命令、结果、阻塞项、复核人和敏感字段禁录清单。
2. 实现 `check_p2a_evidence.py`：只检查结构、允许的状态值和明显秘密键名，不读取 `.env`，不输出匹配到的秘密值。
3. 更新发布规划：P2 总完成仍要求 P2-A + P2-B；当前只执行 P2-A，P2-B 不得从发布门槛消失。
4. 更新路线图：P2-A 完成不改变技术预览、具体 IdP、多机和稳定版口径。

**Run:**

```powershell
python -m pytest apps/api/tests/test_p2a_evidence_contract.py -v
python scripts/check_p2a_evidence.py
git diff --check
```

**Expected:** 检查只输出任务状态摘要，不含秘密或业务正文。

**Commit:** `docs: define p2a validation evidence contract`

### Task A2：验证 HS256 与 OIDC/JWKS HTTP middleware

**Files:**

- Modify: `apps/api/tests/test_auth_optional.py`
- Create: `apps/api/tests/test_oidc_jwks.py`
- Create: `apps/api/tests/p2a_auth_helpers.py`
- Modify: `apps/api/auth/oidc.py`, `apps/api/auth/middleware.py`, `apps/api/auth/run_context.py`
- Modify: `docs/release-validation/p2a-runtime-security-rag-console.md`

**Steps:**

1. 在 test-only `p2a_auth_helpers.py` 提供短寿命 HS256 token builder；测试可复用它，但生产代码和独立脚本不得 import tests。扩充 HTTP 测试：缺 token、伪造签名、错误算法、过期 token、错误 audience、缺 `sub` 或 tenant claim 均返回稳定 `401 unauthorized`；有效 token 进入 middleware 后映射正确 context。
2. middleware 在 auth-required 模式下显式要求非空 `sub` 和 `tenant_id|tid`；不得让后续 route 用 `default` 代替缺失租户。roles/permissions 可为空并继续交给 Policy 安全拒绝。
3. 测试必须在请求前后比较 `RunStore`、`EventLog` 和 `ApprovalStore`，证明被拒绝请求零副作用。
4. 新建进程内 discovery/JWKS fixture：运行时生成临时 RSA key，提供 `/.well-known/openid-configuration` 和 `/jwks/`；测试 issuer、audience、kid、签名、过期和未知 key。
5. 清理 `_openid_config`/`_jwks` 缓存，防止用例之间复用旧 issuer；测试结束关闭 fixture，不写私钥文件。
6. 在证据中记录协议路径与结果数量；不记录 JWT、私钥或 claims 全文。

**Run:**

```powershell
python -m pytest apps/api/tests/test_auth_optional.py apps/api/tests/test_oidc_jwks.py -v
```

**Expected:** 两种认证路径均经 middleware；所有非法 token 为 401 且零副作用；JWKS 测试无外部网络依赖。

**Commit:** `test: validate jwt and oidc middleware contracts`

### Task A3：验证授权、租户隔离、审批复检与审计脱敏

**Files:**

- Modify: `apps/api/tests/test_demo_readonly_policy.py`
- Modify: `apps/api/tests/test_work_order_ops.py`
- Modify: `apps/api/tests/test_approvals_api.py`
- Modify: `apps/api/tests/test_audit_export.py`
- Create: `scripts/verify_p2a_security.py`
- Modify only if tests expose defects: affected routes/domain/core policy code
- Modify: `docs/release-validation/p2a-runtime-security-rag-console.md`

**Steps:**

1. 测试使用 `apps/api/tests/p2a_auth_helpers.py` 建立只读、可创建、可审批、无权限和跨租户五种身份；独立脚本自行生成进程内短寿命 HS256 token，不导入测试模块。两处都只使用脱敏 claims。
2. 验证无权限工具不进入模型可见列表；直接调用仍由 `invoke_tool` 再次拒绝。
3. 验证审批查询、批准/拒绝、超时处理和恢复均按 tenant + approver 权限隔离；拒绝路径不新增工单、台账、业务事件或审批执行记录。
4. 验证审计导出保留 actor、tenant、action、decision、policy version、time/result，但移除 query、token、DSN、password、prompt 和模型全文。
5. `verify_p2a_security.py` 仅运行本地 API 测试客户端并输出计数摘要，不接受或打印真实 token。

**Run:**

```powershell
$env:KNOWLEDGE_BACKEND='fake'
python -m pytest apps/api/tests/test_demo_readonly_policy.py apps/api/tests/test_work_order_ops.py apps/api/tests/test_approvals_api.py apps/api/tests/test_audit_export.py -v
python scripts/verify_p2a_security.py
```

**Expected:** allow/deny/跨租户矩阵通过；拒绝路径零副作用；输出不含禁录字段值。

**Commit:** `test: close security and tenant isolation matrix`

### Task A4：验证平台 pgvector 与只读 RAG-Agent

**Files:**

- Create: `apps/api/tests/test_langchain_pg_live.py`
- Modify: `apps/api/tests/test_rag_agent_pg_retriever.py`
- Modify: `apps/api/tests/test_verify_rag_agent_readonly.py`
- Reuse: `scripts/ingest_demo_rag.py`, `scripts/verify_rag_agent_readonly.py`
- Modify only if tests expose defects: knowledge adapters/factories/lifespan
- Modify: `docs/release-validation/p2a-runtime-security-rag-console.md`

**Environment:**

- `AGENTBRIDGE_TEST_KB_DSN` 指向可销毁的 AgentBridge 专用 pgvector 测试库；不得指向 RAG-Agent 数据库。
- `EMBED_API_BASE=http://127.0.0.1:8080/v1`，模型与 `EMBED_DIMENSIONS` 必须和测试 schema 一致。
- `RAG_AGENT_*` 仅从安全环境注入，不读取或打印其他项目凭证。

**Steps:**

1. 新增 live pytest：只在 `AGENTBRIDGE_TEST_KB_DSN` 存在时运行；在专用测试库中用 `003_knowledge_pgvector.sql` 引导测试 schema，写入带唯一前缀的脱敏文档，验证同租户 citation、跨租户零命中。这里仅准备测试 fixture，不作为发布迁移、升级或回滚证据。
2. 验证 embedding 不可达、维度不匹配和数据库不可达时，health/status 与运行错误可区分，不泄露连接信息。
3. 运行只读 RAG-Agent probe：演示租户至少一个 citation，其他租户零命中；输出键保持固定 allowlist。
4. live pytest 只清理本次唯一前缀测试数据；不得 truncate 共享表。RAG-Agent probe 不执行任何 DDL/DML。

**Run:**

```powershell
python -m pytest apps/api/tests/test_langchain_pg_live.py apps/api/tests/test_rag_agent_pg_retriever.py apps/api/tests/test_verify_rag_agent_readonly.py -v
python scripts/verify_rag_agent_readonly.py
```

**Expected:** live pgvector 用例不得 skip；RAG-Agent demo tenant 有 citation、other tenant 为零；输出无 DSN、文本或向量。

**Commit:** `test: validate pgvector and readonly rag backends`

### Task A5：验证 external RAG HTTP 契约与失败策略

**Files:**

- Modify: `apps/api/tests/test_external_rag_retriever.py`
- Modify: `apps/api/tests/test_ingest_api.py`
- Modify: `apps/api/tests/test_demo_rag.py`
- Create: `scripts/verify_p2a_external_contract.py`
- Modify only if tests expose defects: `apps/api/adapters/external_rag_retriever.py`, knowledge factory/routes
- Modify: `docs/release-validation/p2a-runtime-security-rag-console.md`

**Steps:**

1. 使用注入的 `httpx.MockTransport` 覆盖请求 path、Bearer header、tenant_id、top_k 和响应映射；这会走真实 external adapter，禁止切换到 fake backend。
2. 覆盖 200 空命中、跨租户 hit 丢弃、畸形 JSON、缺字段、401、429、503、网络异常和超时。
3. `empty_hits` 必须只对配置允许的失败返回空；`fail_run` 必须产生稳定、安全、可识别的运行错误，不泄露下游响应正文。
4. 验证 `POST /ingest` 对 external 明确返回 501，且不产生摄取任务或审计成功记录。
5. 脚本输出协议用例计数和状态码矩阵，明确标注“contract-tested；vendor-live deferred to P2-B”。

**Run:**

```powershell
python -m pytest apps/api/tests/test_external_rag_retriever.py apps/api/tests/test_ingest_api.py apps/api/tests/test_demo_rag.py -v
python scripts/verify_p2a_external_contract.py
```

**Expected:** external 成功、空命中和后端不可用三者可区分；501 与失败策略符合文档。

**Commit:** `test: close external rag contract matrix`

### Task A6：验证取消、EventLog 与审批结果投递幂等

**Files:**

- Modify: `apps/api/tests/test_chat_cancel.py`
- Modify: `apps/api/tests/test_threads_and_events.py`
- Modify: `apps/api/tests/test_work_order_ops.py`
- Modify: `packages/core/tests/application/test_event_log_emit_order.py`
- Modify: `packages/core/tests/application/test_lifecycle_projection.py`
- Create: `scripts/verify_p2a_lifecycle.py`
- Modify only if tests expose defects: lifecycle/event/approval implementation

**Steps:**

1. 验证客户端取消后 run 进入稳定终态、释放 thread lock，后续同 thread 请求可以运行；取消前已提交事件可回放，未提交事件不可见。
2. 令 EventLog 在指定 append 序号失败，断言 append-before-SSE、稳定 error/done 语义和无幽灵业务事件。
3. 模拟业务提交成功但结果事件投递失败，断言 approval 保持 `succeeded`、记录 `result_delivery_error`，重试不重复创建工单/台账。
4. 比较 RunStore、EventLog、ApprovalStore 和业务表的最终状态，禁止仅检查 SSE 文本。

**Run:**

```powershell
python -m pytest packages/core/tests/application/test_event_log_emit_order.py packages/core/tests/application/test_lifecycle_projection.py apps/api/tests/test_chat_cancel.py apps/api/tests/test_threads_and_events.py apps/api/tests/test_work_order_ops.py -v
python scripts/verify_p2a_lifecycle.py
```

**Expected:** 取消和失败后无锁泄漏、无重复副作用、无未提交事件外发。

**Commit:** `test: close lifecycle delivery failure matrix`

### Task A7：验证单机限流与依赖健康语义

**Files:**

- Modify: `apps/api/tests/test_rate_limit.py`
- Modify: `apps/api/tests/test_ready.py`
- Modify: `apps/api/tests/test_knowledge_status_provider.py`
- Create: `scripts/verify_p2a_readiness.py`
- Modify only if tests expose defects: middleware/readiness/status providers

**Steps:**

1. 只验证单进程限流：阈值内通过、超限返回 `rate_limited`、窗口后恢复；Redis 跨实例限流不在本任务。
2. 验证 `/health` 仅表示进程存活；`/ready` 对启用依赖返回 ok/degraded/fail，对未启用依赖返回 skipped。
3. 注入 PostgreSQL、embedding、external RAG 和只读 RAG-Agent 的超时/拒绝/异常，断言稳定依赖名和安全消息。
4. readiness 不得返回 DSN、API key、异常堆栈或下游正文；脚本输出每个依赖的状态矩阵。

**Run:**

```powershell
python -m pytest apps/api/tests/test_rate_limit.py apps/api/tests/test_ready.py apps/api/tests/test_knowledge_status_provider.py -v
python scripts/verify_p2a_readiness.py
```

**Expected:** 单机限流和依赖状态语义稳定；文档不暗示 Redis/多机已经验收。

**Commit:** `test: validate single-node limits and readiness`

### Task A8：建立控制台测试工具链并验证权限闭环

**Files:**

- Modify: `apps/web/package.json`, `apps/web/package-lock.json`, `apps/web/vite.config.ts`
- Create: `apps/web/src/test/setup.ts`
- Create: `apps/web/src/App.test.tsx`
- Create: `apps/web/src/features/admin/adminFetch.test.ts`
- Create: `apps/web/src/features/debug/DebugPage.test.tsx`
- Modify only if tests expose defects: `apps/web/src/App.tsx`, routes/admin/debug/auth files
- Modify: `.github/workflows/ci.yml`
- Create: `scripts/verify_p2a_console.py`
- Modify: `docs/release-validation/p2a-runtime-security-rag-console.md`

**Steps:**

1. 先加入 `test` script 和 Vitest/jsdom/React Testing Library dev dependencies，提交 lockfile；测试环境统一从 `src/test/setup.ts` 初始化和清理。
2. `adminFetch.test.ts` 验证 Bearer header、401/403 安全错误、无 token 行为和错误正文不泄露；不得在日志或 snapshot 中保留 token。
3. `App.test.tsx`/页面测试验证管理员与普通用户的导航和禁止页表现。API 权限仍由 A3 验证，前端隐藏不得被当作安全边界。
4. `DebugPage.test.tsx` 使用受控 fetch/SSE fixture 验证发起 run、终端事件、回放入口和错误状态；不得 mock 掉事件解析本身。
5. `verify_p2a_console.py` 使用 TestClient 与 A2/A3 的临时 token 完成 API 闭环：stream run → GET events/replay → audit export；只输出 run/event/audit 数量和状态。
6. CI 新增 `web-tests` job，Node 22.14 下依次执行 `npm ci`、`npm test`、`npm run build`，缓存键使用 `apps/web/package-lock.json`。

**Run:**

```powershell
Push-Location apps/web
npm ci
npm test
npm run build
Pop-Location
python scripts/verify_p2a_console.py
```

**Expected:** Web 测试与构建通过；普通用户无法从 UI 或 API 访问管理资源；API 闭环输出无 token、查询正文或模型全文。

**Commit:** `test: add console release validation gates`

### Task A9：汇总验收、独立审阅与发布口径更新

**Files:**

- Modify: `docs/release-validation/p2a-runtime-security-rag-console.md`
- Modify: `docs/release-plan.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/releases/v0.1.0-tech-preview.md`
- Modify if required: `docs/deploy.md`, `.env.example`

**Steps:**

1. A2–A8 的证据必须包含命令、环境前提、pass/fail/blocked、跳过项和脱敏摘要；A4 live pgvector 或只读 RAG-Agent 任一缺失都使 P2-A 保持未完成。
2. 运行全量自动化门禁：

**Run:**

```powershell
$env:KNOWLEDGE_BACKEND='fake'
python -m pytest packages/core/tests apps/api/tests -q
$base = git merge-base origin/main HEAD
$changedPython = git diff --name-only "$base...HEAD" -- '*.py'
if ($changedPython) { python -m ruff check $changedPython }
python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
python scripts/import_scan_core.py
python scripts/import_scan_rag_engines.py
python scripts/check_p2a_evidence.py
Push-Location apps/web; npm ci; npm test; npm run build; Pop-Location
git diff --check
```

3. 在安全环境变量下复跑 A4 live pgvector 和 RAG-Agent probe；要求相关 live tests 零 skip。不得把 A5 的 contract test 描述成厂商现场联调。
4. 独立审阅 base-to-head diff：重点检查权限绕过、租户泄露、秘密输出、adapter 组装位置、EventLog 顺序和审批幂等；Critical/Important 问题修复后重新审阅。
5. 仅当 A1–A8 全部通过，文档才写 “P2-A 已完成、P2-B 延期”；M11/M12 仍保持发布验收未完全完成，技术预览和已知限制不变。

**Expected:** pytest、架构扫描、Web 门禁和 P2-A 变更路径 Ruff 全绿；live 证据完整、无秘密泄露、工作区只包含本计划预期改动。全仓 Ruff 债务仅作为已记录的 P3 输入，不得伪称已清零。

**Commit:** `docs: record p2a release validation`

## 6. Spec/发布目标映射

| 发布规划要求 | 任务 | 验收证据 |
|---|---|---|
| JWT/OIDC、权限、跨租户、审批超时、审计脱敏 | A2、A3 | HTTP middleware 与零副作用矩阵 |
| pgvector、RAG-Agent、external、501、失败策略、citation | A4、A5 | live pgvector/只读 probe + external contract matrix |
| 断连/取消、EventLog 失败、限流、依赖不可用 | A6、A7 | 状态存储对照与 readiness matrix |
| Web build、管理员/普通用户、调试→回放→审计 | A8 | Vitest/build CI + API 闭环脚本 |
| 部署、迁移/回滚、备份恢复、双实例 | P2-B | 本计划明确不交付 |

## 7. 开工条件

- [ ] 本计划与索引已保存在实施分支或可追踪提交中。
- [ ] 基线 Python/架构门禁和 Web build 可运行。
- [ ] 可生成临时 RSA key；无需修改 Authentik。
- [ ] `AGENTBRIDGE_TEST_KB_DSN` 指向可销毁的 AgentBridge pgvector 测试库。
- [ ] TEI `127.0.0.1:8080` 可达，模型和维度已确认。
- [ ] `RAG_AGENT_*` 可由安全环境提供，且数据库账号只读。
- [ ] Node 22.14/npm 可用；允许通过 lockfile 安装 Vitest/Testing Library 依赖。

除 A4 live 环境外，其余任务不依赖生产部署或多机资源。若 A4 的专用测试库或只读 RAG 凭证不可用，可先完成其他任务，但不得完成 A9。

## 8. Final Plan Audit

- [x] 计划要求每项生产行为先 RED 后 GREEN。
- [x] 每个任务有明确文件、命令、预期结果和独立 commit。
- [x] HS256、JWKS、external contract 与厂商现场验收的口径互不混淆。
- [x] Fake/Memory 回归未被当作 live PostgreSQL/RAG 证据。
- [x] P2-B 延期项仍在发布门槛和已知限制中可见。
- [ ] 完成前执行独立代码审阅和全量门禁。
