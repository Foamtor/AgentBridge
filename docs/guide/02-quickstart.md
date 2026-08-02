# 快速开始

← [为什么用它](./01-why.md) · [文档目录](../INDEX.md) · 下一篇：[基本概念](./03-concepts.md) →

---

## 读完这篇你要达到的状态

本机 API 能起来；用示例插件 **`echo`** 发出一句，能收到流式回复。  

`echo` 只是把你的话原样回出来，**不需要**数据库，也**不需要**真实大模型。  
默认 `.env` 够本地试；其它 demo（如要调模型的）以后再配。

## 你需要什么

- Python **3.12+**
- （可选）Node **18+**：只为打开调试网页
- 本机端口 **8000**（API）、**5173**（网页）尽量空着

如果你装有 Docker，v0.1.0 推荐直接在仓库根目录运行：

```bash
docker compose up --build
```

再打开 <http://127.0.0.1:8080>，选择 `work_order_ops` 体验脱敏工单、图表和审批黄金案例。以下是无需 Docker 的本地开发路径。

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

默认 `.env` 用内存即可本地试；以后要接数据库再改。详见 [部署说明](../deploy.md)。

## 2. 启动 API

```bash
cd apps/api
uvicorn main:app --reload --port 8000
```

浏览器打开，或命令行请求：

```text
http://127.0.0.1:8000/health
```

应看到类似：`{"status":"ok"}`。

## 3.（可选）启动调试台

新开一个终端：

```bash
cd apps/web
npm install
npm run dev
```

打开 <http://127.0.0.1:5173> → 选插件 **`echo`** → 发「你好」。  
能收到回复，就算**本篇**通了（更严的插件验收会看 SSE 里是否出现 `done`，见 [第一个插件](./04-first-plugin.md)）。

## 4. 不用网页：直接打接口

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

更完整的部署（Postgres、鉴权、多机）见 [deploy.md](../deploy.md)、[multi-instance.md](../multi-instance.md)。

---

← [为什么用它](./01-why.md) · [文档目录](../INDEX.md) · 下一篇：[基本概念](./03-concepts.md) →
