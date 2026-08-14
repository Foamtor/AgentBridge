# 常见任务（可复制）

人类版步骤：[guide/02-quickstart.md](../guide/02-quickstart.md)。本文给助手：**命令与路径**。

## 本地起 API

在仓库**根目录**：

```bash
pip install -e "packages/core[dev]" -e "apps/api[dev]"
cp .env.example .env   # Windows PowerShell: copy .env.example .env
python -m uvicorn main:app --app-dir apps/api --reload \
  --reload-dir apps/api --reload-dir packages/core/src --port 8000
```

成功：`GET http://127.0.0.1:8000/health` → 类似 `{"status":"ok"}`。

可选 Web 控制台：

```bash
cd apps/web && npm install && npm run dev
```

打开 `http://127.0.0.1:5173`。默认 `AUTH_MODE=local` 时，先使用 API 启动日志里仅显示一次的 `admin` 初始密码登录并完成强制改密；随后在根页面运行 `work_order_ops` 黄金验证场景。开发自己的插件时打开 `/playground?route=<名字>`；只测最小链路可用 `/playground?route=echo`。

依赖已装好时可用：`.\start-dev.ps1` / `./start-dev.sh`（**不**负责 `pip install` / 复制 `.env`）。

## 冒烟 echo（不依赖网页）

下面的裸 `curl` 和 `scripts/smoke_echo.*` 不携带登录态，只适用于启动 API 前已明确设置 `AUTH_MODE=disabled` 的**非生产隔离开发环境**。默认 `AUTH_MODE=local` 请优先使用登录后的 `/playground`，或为自动化请求实现合法的 Cookie / OIDC 凭据；生产环境禁止关闭认证。

**Windows（PowerShell）：**

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/chat/stream `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"hello\",\"thread_id\":\"t-demo-001\",\"route\":\"echo\"}"
```

**macOS / Linux：**

```bash
curl -N -X POST http://127.0.0.1:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"query":"hello","thread_id":"t-demo-001","route":"echo"}'
```

或：`scripts/smoke_echo.ps1` / `scripts/smoke_echo.sh`。

## 加一个业务插件

清单：[02-domain-development.md](./02-domain-development.md)。  
细节：[add-a-domain.md](../add-a-domain.md)。

最短路径：复制 `_scaffold` → 改名 → 登记 `apps/api/domains/bootstrap.py` → 重启 → 新 `route` 冒烟。

## 接外部知识库（RAG）

代码支持 `KNOWLEDGE_BACKEND=external`（HTTP 检索适配器在 `apps/api/adapters`，**由 lifespan 调用工厂组装**，不是 domain 里 new）：

1. `.env`：`KNOWLEDGE_BACKEND=external`  
2. 设 `KB_EXTERNAL_BASE_URL`（对方提供检索 HTTP；字段以对接协议 / `.env.example` / 代码为准）  
3. 业务插件只用已注入的 `retriever`（如 `ctx.metadata["retriever"]`），**不要**在 domain 再写一套客户端  
4. **跑平台自测时**改回 `KNOWLEDGE_BACKEND=fake`，或临时去掉该变量  

说明：[knowledge-base.md](../knowledge-base.md)、`.env.example`。文档与代码冲突时：以代码与完整方案为准，并应回修文档。

## 查接口与事件

| 需求 | 文档 |
|------|------|
| HTTP 路由 | [api-reference.md](../api-reference.md) |
| SSE 事件字段 | [contracts.md](../contracts.md) |
| 部署 / Postgres / 鉴权 | [deploy.md](../deploy.md) |
| 多机 | [multi-instance.md](../multi-instance.md) |

## 改完如何自证

见 [04-testing.md](./04-testing.md)。
