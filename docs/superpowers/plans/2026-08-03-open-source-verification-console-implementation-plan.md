# AgentBridge 开源验证工作台 Implementation Plan

> **状态：** P0-P6 已完成；P7 Compose 真实闭环暂缓（由用户统一处理）  
> **日期：** 2026-08-03  
> **Spec：** [实施 Spec](../specs/2026-08-03-open-source-verification-console-implementation-spec.md)  
> **功能设计：** [功能设计](../specs/2026-08-03-open-source-verification-console-functional-design.md)  
> **执行方式：** 当前会话内联分批，TDD；每个任务先红测试、再实现、再复核

## 1. Goal

让首次 clone 的开发者通过安全管理员首登进入桌面验证工作台，在同一工作台完成 `work_order_ops` 查询、图表、知识引用、审批草稿、批准创建和幂等复读，并可展开平台证据和高级调试能力。

## 2. Non-goals

- 不实现普通用户注册、邮件找回、MFA、WebAuthn、多管理员/组织管理。
- 不把 Authentik/OIDC 变成默认 Compose 依赖；OIDC 仅保留兼容和后续企业模式。
- 不修改 `packages/core` 的业务语义或引入本地密码逻辑。
- 不做移动布局；仅验证 1024/1280/1440/1600px 桌面视口。
- 不发布 PyPI/npm/GHCR，不做生产多机、备份恢复或完整 IdP 联调。

## 3. 全局硬约束

- 认证 Store Port 在 `apps/api/auth/ports.py`；Postgres 实现在 `apps/api/adapters/`；创建和注入只在 `lifespan.py`。
- `agentbridge_core.application` 不 import adapters；core 不写 `work_order_ops`、`console_admin` 或 HTTP Cookie 名称。
- 业务 domain 不持有 `EventSink`，不创建适配器；Web 只消费已提交事件。
- 默认 Compose 使用 `AUTH_MODE=local`；`AUTH_MODE=disabled` 只能由测试 fixture 显式启用，生产环境启动拒绝。
- 初始密码每安装随机、只在首次创建日志显示一次；任何数据库、API、Web、审计和错误响应不得包含密码明文。
- 所有密码操作服务端最终校验，Argon2id 哈希；会话 Cookie HttpOnly、SameSite、HTTPS 下 Secure。
- 默认桌面最小内容宽度 1024px；小于该宽度不重排为移动布局。
- 每个任务完成后先 `git diff --check`，再跑任务级测试；不撤销工作区已有用户改动。

## 4. 任务依赖

| 任务 | 内容 | 依赖 |
|------|------|------|
| P0 | 认证依赖、配置和迁移骨架 | 无 |
| P1 | Store Port、Fake/Postgres 适配器、密码服务 | P0 |
| P2 | 初始化管理员、会话中间件和认证 API | P1 |
| P3 | `/console/bootstrap`、审批 GET 与认证契约 | P2 |
| P4 | Web session guard、登录、首次改密、国际化 | P2 |
| P5 | VerificationRun reducer 和黄金结果渲染 | P3、P4 |
| P6 | 应用壳、桌面工作台、管理/契约兼容导航 | P5 |
| P7 | Compose、文档、端到端 smoke 和全量门禁 | P6 |

## 5. 任务详单

### Task P0：依赖、配置与迁移骨架

**Files:**

- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/config/settings.py`
- Create: `apps/api/migrations/009_console_auth.sql`
- Modify: `.env.example`
- Create: `apps/api/tests/test_console_auth_migration.py`

**TDD steps:**

1. 先写测试，断言配置能解析 `AUTH_MODE=local|oidc|disabled`、Cookie/TTL/Argon2 参数和生产 disabled 拒绝。
2. 先写迁移形状测试，断言三个表、约束、索引和幂等执行；不得在 SQL 中插入固定密码。
3. 增加 `argon2-cffi` 依赖和配置默认值；新增迁移，仅创建表。
4. 运行迁移测试，确认已有 `001`–`008` 新 volume 顺序兼容。

**Verify:**

```text
python -m pytest apps/api/tests/test_console_auth_migration.py -q
git diff --check
```

**Review checkpoint:** 配置默认值不能让生产误进入 disabled；迁移不能把一次性密码写入仓库。

### Task P1：认证 Store Port、Fake/Postgres 适配器和密码服务

**Files:**

- Create: `apps/api/auth/ports.py`
- Create: `apps/api/auth/passwords.py`
- Create: `apps/api/auth/local_admin.py`
- Create: `apps/api/adapters/postgres_console_auth.py`
- Create: `apps/api/testing/fake_console_auth.py`
- Create: `apps/api/tests/test_console_auth_service.py`
- Create: `apps/api/tests/test_postgres_console_auth.py`
- Modify: `apps/api/lifespan.py`

**TDD steps:**

1. 写失败单测：首次 ensure 生成一次密码，重复 ensure 不生成；密码策略和 Argon2id verify/rehash 矩阵；session hash 不等于原 token。
2. 写失败适配器契约测试，Fake 与 Postgres Store 对 admin/session/attempts 的返回和并发语义一致。
3. 实现 `ConsoleAuthStore` Port，方法只表达管理员、会话和限速数据，不暴露 asyncpg 类型给 auth service。
4. 在 `apps/api/adapters` 实现 Postgres；在 lifespan 创建并注入；测试通过 fixture 注入 Fake。
5. 实现密码服务、一次性凭据生成、强度策略、渐进限速和恢复轮换命令。

**Verify:**

```text
python -m pytest apps/api/tests/test_console_auth_service.py apps/api/tests/test_postgres_console_auth.py -q
python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
python scripts/import_scan_core.py
```

**Review checkpoint:** `auth/` 不 import `apps.api.adapters`；只有 `lifespan.py` new 适配器；日志捕获测试确认明文只有一次输出。

### Task P2：本地会话中间件与认证 API

**Files:**

- Create: `apps/api/auth/session.py`
- Create: `apps/api/routes/auth.py`
- Modify: `apps/api/main.py`
- Modify: `apps/api/auth/middleware.py`
- Modify: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/test_console_auth_api.py`
- Create: `apps/api/tests/test_console_auth_middleware.py`

**TDD steps:**

1. 写 HTTP 失败测试：anonymous session、错误登录、限速、password-change 只允许改密、authenticated 访问受保护 API、logout/过期/撤销。
2. 写 Cookie 和 CSRF/Origin 失败测试：HttpOnly、SameSite、Secure 条件、no-store、跨站 POST 拒绝。
3. 实现 session context 注入，将 local admin 映射到现有 `RunContext`；OIDC 分支继续调用现有 Bearer 校验。
4. 挂载四个 `/auth/*` 路由；实现统一安全错误码，不泄露账号存在性。
5. 增加 CLI reset 入口和审计 hook；恢复后撤销会话并要求改密。

**Verify:**

```text
python -m pytest apps/api/tests/test_console_auth_api.py apps/api/tests/test_console_auth_middleware.py -q
python -m pytest apps/api/tests -q
```

**Review checkpoint:** 认证路由不绕过租户/权限边界；受限改密 Cookie 不能调用 chat、admin 或 approval。

### Task P3：控制台快照、审批恢复查询和契约

**Files:**

- Create: `apps/api/routes/console.py`
- Modify: `apps/api/routes/approvals.py`
- Modify: `apps/api/main.py`
- Modify: `docs/contracts.md`
- Create: `apps/api/tests/test_console_bootstrap.py`
- Modify: `apps/api/tests/test_approvals_api.py`

**TDD steps:**

1. 写失败测试：bootstrap 未登录拒绝、登录后返回真实 runtime/auth mode/reference metadata 且无秘密；参考 domain 缺失时 available=false。
2. 写审批 GET 测试：同租户原请求人可读、approval:decide 可读、跨租户/不存在 404、查询不改变状态且不 claim。
3. 实现 console route，从 app state catalog/settings/RunContext 做安全投影。
4. 把审批公共投影抽成复用函数，增加 GET，不改变现有 POST 决策语义。
5. 更新 contracts 与 API 错误码表。

**Verify:**

```text
python -m pytest apps/api/tests/test_console_bootstrap.py apps/api/tests/test_approvals_api.py -q
```

**Review checkpoint:** bootstrap 不通过 JWT 解码猜权限、不返回 DSN/Token；approval GET 绝不触发执行。

### Task P4：Web session guard、登录、改密和 i18n

**Files:**

- Create: `apps/web/src/features/auth/session.ts`
- Create: `apps/web/src/features/auth/LoginPage.tsx`
- Create: `apps/web/src/features/auth/ChangePasswordPage.tsx`
- Create: `apps/web/src/features/auth/ProtectedRoute.tsx`
- Create: `apps/web/src/i18n/index.ts`
- Create: `apps/web/src/i18n/zh-CN.ts`
- Create: `apps/web/src/i18n/en.ts`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/routes/index.tsx`
- Modify: `apps/web/src/features/auth/token.ts`
- Create: `apps/web/src/features/auth/LoginPage.test.tsx`
- Create: `apps/web/src/features/auth/ProtectedRoute.test.tsx`

**TDD steps:**

1. 写组件失败测试：session 三态路由、登录错误/限速、强制改密、成功后进入 `/`、登出回到 `/login`。
2. 写安全测试：密码不进入 localStorage、URL 或 fetch 日志；切换语言覆盖主要登录流程；服务端错误码映射。
3. 实现统一 session fetch 层，所有 API 使用 `credentials: "include"`；删除默认无 Token 即 admin 的 Web 侧判断。
4. 实现登录和改密页，强度提示只做辅助，按钮由服务端响应决定；实现桌面最小宽度提示。
5. 将旧手动 Bearer 输入移入 advanced OIDC/debug 模式，保留清除和 password input。

**Verify:**

```text
pnpm --dir apps/web test -- LoginPage ProtectedRoute
pnpm --dir apps/web build
```

**Review checkpoint:** 未登录首屏不出现工作台或管理数据；主流程中英文不混杂；不保存会话令牌到 localStorage。

### Task P5：VerificationRun reducer 和黄金结果

**Files:**

- Create: `apps/web/src/features/verification/types.ts`
- Create: `apps/web/src/features/verification/reducer.ts`
- Create: `apps/web/src/features/verification/useVerificationRun.ts`
- Create: `apps/web/src/features/verification/BusinessResults.tsx`
- Create: `apps/web/src/features/verification/PlatformEvidence.tsx`
- Create: `apps/web/src/features/verification/ApprovalDecision.tsx`
- Create: `apps/web/src/features/verification/reducer.test.ts`
- Create: `apps/web/src/features/verification/BusinessResults.test.tsx`
- Modify: `apps/web/src/lib/sseClient.ts`

**TDD steps:**

1. 写 reducer 失败测试：sequence 去重/排序、稳定终态、approval_required 暂停、未知扩展保留、断线待恢复。
2. 写结果组件失败测试：list/chart/citation/draft/created、chart fallback、truncated、原始 JSON 折叠。
3. 实现 reducer 与 hook；禁止各组件 reverse-scan 事件。
4. 实现业务结果与平台证据两区；审批组件使用 POST 决策和 GET 恢复，防重复点击。
5. 为 ECharts 保留纯 JSON option，渲染失败退化为值列表。

**Verify:**

```text
pnpm --dir apps/web test -- reducer BusinessResults
pnpm --dir apps/web build
```

**Review checkpoint:** 业务结果优先可读，技术证据可展开；未知事件不阻塞；审批未知状态不自动重试写入。

### Task P6：应用壳、桌面验证工作台和兼容入口

**Files:**

- Create: `apps/web/src/features/verification/VerificationWorkbench.tsx`
- Create: `apps/web/src/features/verification/EnvironmentSummary.tsx`
- Create: `apps/web/src/features/verification/ScenarioPicker.tsx`
- Create: `apps/web/src/features/verification/AdvancedDebug.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/routes/index.tsx`
- Modify: `apps/web/src/features/admin/OverviewPage.tsx`
- Modify: `apps/web/src/styles.css`
- Modify: `apps/web/src/App.test.tsx`
- Create: `apps/web/src/features/verification/VerificationWorkbench.test.tsx`

**TDD steps:**

1. 写页面失败测试：`/` 工作台、`/debug` 兼容重定向、`/admin` 次级入口、契约入口、全局语言和退出。
2. 写场景测试：一次点击设置正确 route/query/extra；运行中禁用重复发送；cancel 保留证据。
3. 实现应用壳与桌面布局，默认不显示 thread/Token/409；高级区完整保留。
4. 实现环境摘要消费 `/ready` + `/console/bootstrap`，ready/degraded/blocked 显示真实状态。
5. 管理页面迁移到 `/admin` 命名空间并提供旧路径兼容重定向；不重做后台内部功能。
6. 在 1024/1280/1440/1600px 视口检查溢出、表格滚动、焦点和 aria-live 状态。

**Verify:**

```text
pnpm --dir apps/web test
pnpm --dir apps/web build
```

**Review checkpoint:** 首屏三分钟路径没有被管理卡片或 raw protocol 打断；Web 仍是开发者工具，不是业务产品。

### Task P7：Compose、文档和全量 TDD 门禁

> 当前仅剩真实 Docker Compose smoke；用户已决定暂缓并统一处理 Docker Engine 权限。其余 P7 文档、配置和自动化门禁已完成。

**Files:**

- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `Dockerfile`
- Modify: `docs/deploy.md`
- Modify: `infra/authentik/README.md`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/contracts.md`
- Modify: `scripts/verify_compose_stack.py`
- Create: `apps/api/tests/test_v01_console_verification.py`
- Create: `apps/web/src/features/verification/compose-flow.test.ts`

**TDD steps:**

1. 先写 Compose/API smoke：新 volume 初始化、捕获一次性密码、登录、改密、`/console/bootstrap`、查询/图表、草稿、审批、创建和 GET 恢复。
2. 更新 Compose 默认 `AUTH_MODE=local`、健康检查和 API/Web 同源 Cookie 代理；不得把密码写入 compose YAML。
3. 文档说明 `docker compose up --build`、查看一次性密码、首次改密、恢复命令、退出和重置演示 volume 的数据影响。
4. README 把“需要管理员首登”写进 Quick Start，不展示实际示例密码；OIDC 仍标为可选进阶。
5. 执行全量门禁，复核 git diff 和敏感字段扫描；不提交 `.env`、密码、Cookie、volume 或原型服务产物。

**Verify:**

```text
python -m pytest packages/core/tests apps/api/tests -q
python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
python scripts/import_scan_core.py
pnpm --dir apps/web test
pnpm --dir apps/web build
python scripts/check_release_docs.py
docker compose config --quiet
   python scripts/verify_compose_stack.py --golden-case --remove-demo-volume
git diff --check
```

**Review checkpoint:** 新环境完整闭环真实通过；日志、网络响应和截图没有凭据；默认开发流程与 README、Spec、Plan 一致。

## 6. 完成定义

- P0–P7 每项测试先红后绿，并在任务级 checkpoint 复核。
- 新安装只生成一次性 admin 密码，完成改密后无认证 dev 超级管理员路径。
- 认证状态、租户权限、审批恢复、业务结果和技术证据在 Web/API 测试中都有覆盖。
- Compose smoke 完成“初始化 -> 登录 -> 改密 -> 查询/图表 -> 草稿 -> 审批 -> 创建 -> 恢复”。
- `packages/core` import 门禁和业务名扫描通过。
- 桌面视口 1024/1280/1440/1600px 无关键溢出；移动端不在验收范围。
- README、部署文档、contracts 和 Authentik 说明与真实配置一致。
- 未创建 commit、分支合并或 GitHub 推送，除非用户单独授权。

确认本 Plan 后，开始 P0，按任务逐项执行，不跨阶段一次性改完所有文件。
