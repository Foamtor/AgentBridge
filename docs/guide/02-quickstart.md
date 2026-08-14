# 快速开始

← [为什么用它](./01-why.md) · [文档目录](../INDEX.md) · 下一篇：[基本概念](./03-concepts.md) →

---

## 读完这篇你要达到的状态

用根目录 Compose 启动自托管实例，完成首次管理员登录，并在验证工作台跑通 `work_order_ops`。

默认体验不需要真实大模型或外部知识库；PostgreSQL、离线模型和合成业务数据由 Compose 一起启动。`echo` 仍保留为插件调试台中的最小链路测试。

## 你需要什么

- Python **3.12+**
- （可选）Node **18+**：仅在不用 Compose、单独开发 Web 时需要
- 本机端口 **8000**（API）、**5173**（网页）尽量空着

如果你装有 Docker，v1.0.0 推荐直接在仓库根目录运行：

```bash
docker compose up --build
```

从 `docker compose logs api` 取得仅显示一次的 `admin` 初始密码，再打开 <http://127.0.0.1:8080> 登录并完成强制改密。根页面就是 Verification Workbench，可直接体验 `work_order_ops` 的脱敏工单、图表、知识检索和审批黄金案例。以下是不用 Compose 启动代码进程的本地开发路径。

建议在虚拟环境里装依赖（可选但省事）：`python -m venv .venv` 后激活再执行下面的 `pip`。

## 1. 安装

在仓库**根目录**：

```bash
pip install -e "packages/core[dev]" -e "apps/api[dev]"
cp .env.example .env
```

Windows PowerShell 复制环境文件：

```powershell
copy .env.example .env
```

默认 `.env` 使用本地管理员认证和 PostgreSQL 持久化；本地开发前需要准备可访问的 PostgreSQL，并按需填写 `PG_*`。如只做无认证、无外部调用的隔离测试，可临时使用 `AUTH_MODE=disabled`，但生产环境禁止关闭认证。详见 [部署说明](../deploy.md)。

## 2. 启动 API

```bash
python -m uvicorn main:app --app-dir apps/api --reload \
  --reload-dir apps/api --reload-dir packages/core/src --port 8000
```

浏览器打开，或命令行请求：

```text
http://127.0.0.1:8000/health
```

应看到类似：`{"status":"ok"}`。

## 3.（可选）启动 Web 控制台

新开一个终端：

```bash
cd apps/web
npm install
npm run dev
```

打开 <http://127.0.0.1:5173>，使用 API 启动日志中的一次性 `admin` 密码登录并完成强制改密。根页面运行黄金验证场景；测试最小插件链路时进入 `/playground?route=echo` 发「你好」。能看到流式回复和完成状态，就算**本篇**通了（更严的插件验收见 [第一个插件](./04-first-plugin.md)）。

## 4. 不用网页：直接打接口

以下命令不携带登录态，只适用于启动 API 前已明确设置 `AUTH_MODE=disabled` 的**非生产隔离开发环境**。默认 `AUTH_MODE=local` 应携带合法会话 Cookie；OIDC 模式应携带合法 Bearer Token。

PowerShell 示例：

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/chat/stream `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"hello\",\"thread_id\":\"t-demo-001\",\"route\":\"echo\"}"
```

macOS / Linux：

```bash
curl -N -X POST http://127.0.0.1:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"query":"hello","thread_id":"t-demo-001","route":"echo"}'
```

会持续返回 SSE 事件（一边生成一边推）。字段说明见 [contracts.md](../contracts.md)。

仓库冒烟脚本：`scripts/smoke_echo.ps1` / `scripts/smoke_echo.sh`。

## 一键脚本

依赖已按上面装好之后，可用根目录 `.\start-dev.ps1`（Windows）或 `./start-dev.sh` 起 API（有 Node 时顺带起网页）。  
脚本**不会**替你 `pip install` / 复制 `.env`。

## 常见翻车

| 现象 | 可先检查 |
|------|----------|
| 端口被占用 | 换端口，或关掉占用 8000/5173 的进程 |
| 知识相关测试行为怪 | 本地 `.env` 若写了 `KNOWLEDGE_BACKEND=external`，测平台自测请改回 `fake` 或先去掉该变量 |
| `import agentbridge_core` 指到旧目录 | 在本仓库根目录重装：`pip install -e "packages/core[dev]" -e "apps/api[dev]"` |
| 网页能开但接口不通 | 确认 API 已起在 8000；开发时代理默认指向 `127.0.0.1:8000` |
| `/chat/stream` 返回 401 | 默认是 `AUTH_MODE=local`；先登录 Web，或为自动化请求提供合法 Cookie / OIDC Token |

更完整的部署（Postgres、鉴权、多机）见 [deploy.md](../deploy.md)、[multi-instance.md](../multi-instance.md)。

---

← [为什么用它](./01-why.md) · [文档目录](../INDEX.md) · 下一篇：[基本概念](./03-concepts.md) →
