# AgentBridge 开源验证工作台实施 Spec

> **状态：** 待确认  
> **日期：** 2026-08-03  
> **输入：** [用户故事板](../storyboards/2026-08-03-open-source-verification-console.md)、[功能设计](2026-08-03-open-source-verification-console-functional-design.md)、[HTML 原型](../../prototypes/2026-08-03-verification-workbench.html)  
> **后续：** 本 Spec 确认后再制定 Plan，并以 TDD 执行

## 1. 目标与边界

把现有 `apps/web` 从“默认 echo 调试页 + 管理总览”升级为登录后开源验证工作台，完成以下可验收闭环：

```text
一次性管理员凭据 -> 登录 -> 强制设置新密码 -> 环境快照
  -> 一键运行 work_order_ops 只读 / 知识场景
  -> 审批前草稿 -> 人工批准 -> 工单 + 台账幂等结果
  -> 平台证据与插件开发入口
```

本 Spec 不实现客户业务前端、用户注册、邮件找回、生产 IdP 管理、多机会话、移动布局或包发布工程。`packages/core` 不增加本地认证逻辑，不写入 `work_order_ops` 名称。

## 2. 交付结构

### API 宿主

- `apps/api/auth/local_admin.py`：管理员初始化、Argon2id 哈希、密码策略、会话服务和恢复命令调用逻辑；只依赖认证 Store Port。
- `apps/api/auth/session.py`：同源 Cookie 会话解析、受限改密会话、过期与撤销；不创建数据库适配器。
- `apps/api/routes/auth.py`：`/auth/session`、`/auth/login`、`/auth/change-password`、`/auth/logout`。
- `apps/api/routes/console.py`：`GET /console/bootstrap`，只读运行快照。
- `apps/api/routes/approvals.py`：增加 `GET /approvals/{approval_id}`，复用现有 `ApprovalPublic` 投影。
- `apps/api/migrations/009_console_auth.sql`：管理员、会话、失败限速表。
- `apps/api/auth/ports.py`：管理员、会话和登录限速的异步 Port 协议。
- `apps/api/adapters/postgres_console_auth.py`：PostgreSQL Store 适配器；只由 `lifespan.py` 创建。
- `apps/api/testing/fake_console_auth.py`：测试用 fake Store；仅由 fixture 注入。
- `apps/api/config/settings.py`：新增 `AUTH_MODE`、Cookie、初始凭据和密码策略配置；保留 OIDC 配置。
- `apps/api/main.py` / `apps/api/lifespan.py`：创建 Store 适配器、组装认证服务、挂载认证路由和启动初始化；不在 domain、application 或 core 创建实现。
- `apps/api/pyproject.toml`：增加 `argon2-cffi`；锁文件与镜像依赖同步。

### Web

- `apps/web/src/features/auth/`：session hook、登录页、首次改密页、退出和 401/403 路由保护。
- `apps/web/src/features/verification/`：工作台、环境摘要、场景选择、运行 reducer、业务结果、技术证据、审批恢复。
- `apps/web/src/features/debug/`：保留高级调试能力，改为工作台的折叠区域；删除默认首屏的 echo/hello 入口。
- `apps/web/src/i18n/`：中英文资源和 locale 持久化。
- `apps/web/src/routes/index.tsx` / `App.tsx`：登录前、强制改密、工作台、契约和管理路由分层。
- `apps/web/src/styles.css`：桌面端 1024px 以上布局；小于 1024px 保持结构并允许横向滚动，不增加移动断点。

### 文档与配置

- `docker-compose.yml`：默认 API 使用 `AUTH_MODE=local`；不再用无认证 dev 超级管理员跑默认 Web。
- `.env.example`、`docs/deploy.md`、`infra/authentik/README.md`：说明本地认证、一次性密码取用、恢复命令和 OIDC 替代模式。
- `docs/contracts.md`：登记认证、会话 Cookie、bootstrap 和审批查询契约。

## 3. 认证状态与数据模型

### 管理员初始化

启动生命周期在数据库迁移完成后调用 `ensure_console_admin()`：

1. 查询 `console_admins` 中固定用户名 `admin`；存在则不生成密码、不写日志。
2. 不存在时使用 `secrets.token_urlsafe(24)` 生成初始密码，Argon2id 哈希后插入，设置 `must_change_password=true`。
3. 明文只通过受控 logger 输出一次，日志字段使用固定前缀，禁止结构化日志收集器重复渲染。
4. 返回初始化结果给 lifespan 仅用于审计；不放入 `app.state`、健康接口或 Web 响应。

恢复命令在同一服务中调用 `rotate_initial_password()`，要求交互确认或显式环境确认变量；完成后撤销所有会话并将账号重新置为强制改密。

### 密码策略

服务端函数 `validate_password(candidate, username, current_hash)` 是唯一权威：

- 长度 12 至 128 个 Unicode 字符；
- 拒绝 `admin`、常见密码词表和仓库内置离线泄露列表命中；
- 拒绝与当前密码相同；
- 使用确定性离线强度评分达到 `strong`；前端只复用可解释规则展示反馈；
- 错误返回机器码 `password_too_short`、`password_too_long`、`password_common`、`password_contains_username`、`password_reused`、`password_too_weak`，不返回候选密码或评分细节。

Argon2id 哈希参数通过配置提供最低值和算法版本，登录成功时若参数低于当前基线则透明 rehash。测试使用固定低成本参数，生产默认参数必须经过启动基准校验。

### 表结构

`009_console_auth.sql`：

```sql
CREATE TABLE console_admins (
  username TEXT PRIMARY KEY,
  password_hash TEXT NOT NULL,
  must_change_password BOOLEAN NOT NULL DEFAULT TRUE,
  password_version INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  password_changed_at TIMESTAMPTZ
);

CREATE TABLE console_sessions (
  session_hash TEXT PRIMARY KEY,
  username TEXT NOT NULL REFERENCES console_admins(username),
  kind TEXT NOT NULL CHECK (kind IN ('password_change', 'authenticated')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ
);

CREATE TABLE console_login_attempts (
  bucket_key TEXT PRIMARY KEY,
  failures INTEGER NOT NULL DEFAULT 0,
  first_failure_at TIMESTAMPTZ,
  last_failure_at TIMESTAMPTZ
);
```

会话只保存 SHA-256(session token)；Cookie 原值为至少 256 bit CSPRNG。默认空闲过期 12 小时、绝对过期 24 小时，改密会话 15 分钟。清理任务删除已过期或已撤销记录，不影响审批状态。

## 4. HTTP 契约

### 认证接口

未登录可访问 `GET /health`、`GET /ready`、`GET /auth/session`、`POST /auth/login`；静态 Web 页面由 nginx 返回，但工作台 API 必须鉴权。

`GET /auth/session`：

```json
{"status":"anonymous"}
{"status":"password_change_required","username":"admin"}
{"status":"authenticated","username":"admin","permissions":["*"]}
```

`POST /auth/login` 请求：`{"username":"admin","password":"..."}`。成功返回 `{"status":"password_change_required"}` 或 `{"status":"authenticated"}` 并设置 `agentbridge_session` Cookie。失败统一为 401 `auth_invalid_credentials`；限速为 429 `auth_rate_limited`。

`POST /auth/change-password` 请求：`{"current_password":"...","new_password":"..."}`。受限会话可使用初始密码作为 current；成功返回 authenticated 状态并轮换 Cookie。策略错误为 422，响应只含安全错误码。

`POST /auth/logout` 撤销当前会话，重复调用返回 204。

所有 POST 认证接口检查 `Origin` 或可信同源 `Sec-Fetch-Site`，设置 `Cache-Control: no-store`，不允许密码出现在日志、URL、审计 payload、Sentry 或前端状态持久化。

### 控制台快照

`GET /console/bootstrap` 要求 authenticated session，返回 `release`、`runtime`、当前 `context` 和 reference metadata；不返回 DSN、密钥、密码、Token 或未过滤工具列表。`runtime.auth_mode` 取 `local|oidc|disabled`，不得继续返回与实际不符的 `auth_required=false`。

### 审批查询

`GET /approvals/{approval_id}` 要求当前租户，且调用方是原请求人、具备 `approval:decide` 或管理读取权限。跨租户和不存在统一为 404；只读，不 claim、不恢复、不执行。

## 5. API 中间件与权限边界

认证顺序：

```text
health/ready/static -> public
auth/session/login -> local auth endpoint
all other API -> session cookie (local) or validated Bearer JWT (oidc) -> RunContext -> existing Policy
```

`AUTH_MODE=disabled` 只允许测试 fixture 显式设置；启动时若 `ENVIRONMENT=production` 直接拒绝。默认 Compose 为 `local`。本地会话映射到 `user_id=admin`、`tenant_id=dev`、`roles=[admin]`、`permissions=[*]`，但这个映射由 API host 完成，core 只接收 context。

管理路由继续使用现有 `admin:*` 权限检查；工作台只读/审批场景分别由 domain 声明权限和 lifecycle 二次鉴权。Web 不通过解码 JWT 或猜测 Cookie 判断管理员能力。

## 6. Web 状态与组件实现

### 路由

- `/login`：anonymous。
- `/setup-password`：仅 `password_change_required`。
- `/`：仅 `authenticated`，验证工作台。
- `/contracts`：仅 `authenticated`，契约参考。
- `/admin/*`：仅 `authenticated` 且通过现有 admin permission guard。
- `/debug`：重定向到 `/?mode=advanced`，保留兼容。

首屏请求 `GET /auth/session`；401/403 由统一 fetch 层触发路由迁移。刷新不得把本地缓存当成认证凭据。

### VerificationRun reducer

`useVerificationRun` 统一接收 SSE 和审批响应：按 sequence 去重/排序，输出 `status`、`results`、`approval`、`safeError`。组件不得各自 reverse-scan 事件或把 HTTP 完成当业务完成。

### 业务结果映射

- `x.work_order_ops.list` -> 可滚动表格；`truncated` 显示截断标识。
- `x.work_order_ops.chart` -> ECharts option；异常退化为类别/数值列表。
- `x.bridge.citation` -> 引用列表；无来源不显示虚假链接。
- `x.work_order_ops.ledger_preview` + `x.bridge.approval_required` -> 草稿与审批区。
- `x.work_order_ops.work_order_created` -> 成功摘要与幂等复读入口。
- 未知 `x.*` -> 技术证据原始 JSON，不阻塞其他结果。

### 桌面布局

目标视口 1024/1280/1440/1600px；不新增移动断点。小于 1024px 保持最小内容宽度并显示桌面提示，关键结果允许横向滚动。

## 7. 兼容与迁移

- 旧 `AUTH_REQUIRED=false` 和无 Token 自动 dev admin 只保留给测试 fixture；Compose、README 和部署示例切换到 `AUTH_MODE=local`。
- 旧手动 Bearer 继续在 `AUTH_MODE=oidc` 或显式 advanced debug fixture 可用；本地会话不暴露可复制 Token。
- 旧 `/debug` 和后台旧路径提供一次兼容重定向，避免旧链接失效。
- migrations 必须按编号在全新 volume 运行；已有 volume 需要提供 `009_console_auth.sql` 的显式升级说明。
- 不删除旧认证环境变量，迁移期记录映射规则和弃用时间。

## 8. TDD 验收矩阵

### API 单元与集成测试

- 首次初始化只生成一次密码；重启/重复 lifespan 不重新输出。
- 初始密码哈希验证成功，数据库和日志测试 fixture 不出现明文以外的预期单次捕获值。
- 密码策略覆盖长度、Unicode、常见密码、用户名、复用、强度和边界 128 字符。
- session token 不可预测、只存哈希；过期、撤销、空闲续期和绝对过期正确。
- anonymous、password-change、authenticated 三种状态的路由保护矩阵完整。
- 登录错误统一 401；限速按账号/IP 生效，成功后恢复。
- 改密事务同时更新哈希、标志和会话；并发改密只有一个成功。
- logout 幂等；跨站 Origin 被拒绝；Cookie 属性完整。
- `AUTH_MODE=local|oidc|disabled` 启动校验和 production disabled 拒绝。
- bootstrap 不泄露秘密；approval GET 做租户/权限隔离且只读。

### Web 单元与组件测试

- 未登录、强制改密、已登录路由切换和 401/403 recovery。
- 密码强度反馈与服务端错误码映射；不把密码写入 localStorage 或 URL。
- 三个场景一键运行；running/cancelled/succeeded/failed 状态。
- list/chart/citation/draft/approval/created 事件 reducer 与未知事件折叠。
- 审批批准、拒绝、网络不确定后 GET 恢复和幂等结果复读。
- 中英文主流程完整；1024/1280/1440/1600px 无溢出。

### 门禁

```text
python -m pytest packages/core/tests apps/api/tests -q
python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
python scripts/import_scan_core.py
pnpm --dir apps/web test
pnpm --dir apps/web build
python scripts/check_release_docs.py
```

新增认证与工作台测试必须先红后绿；Compose smoke 在新 volume 上验证：初始化凭据 -> 登录 -> 改密 -> 查询/图表 -> 草稿 -> 审批 -> 创建 -> GET 恢复。

## 9. 不在本 Spec 内的决定

- OIDC PKCE 的完整生产联调和 Authentik blueprint 自动配置；
- 多管理员、角色编辑、组织/租户管理；
- 密码邮件找回、MFA、WebAuthn；
- 分布式 session store 和多机部署；
- 移动端布局。

确认本 Spec 后，下一阶段将把上述文件拆成按依赖顺序执行的 TDD Plan；在 Plan 确认前不修改生产代码。
