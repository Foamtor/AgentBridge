# 第一个业务插件

← [基本概念](./03-concepts.md) · [文档目录](../INDEX.md) · 下一篇：[AI 控制台](./05-console.md) →

---

## 目标（人话）

加一个**自己的**业务文件夹，注册之后，用新的 `route` 名字能聊上几句。

细节逐步清单以 [怎么加业务插件](../add-a-domain.md) 为准；本文只告诉你：**先看哪、改哪、怎样算成功**。

## 成功标准

- 调试台下拉框里能选到你的 `route`，发一句有回复；**或**
- `POST /chat/stream` 里 `"route":"<你的名字>"` 能收到 SSE，并出现结束事件（类型名一般是 `done`）

## 建议最短路径

1. **先看懂样板，再复制空壳**  
   - 理解最小形态：读 `apps/api/domains/echo/`（无工具、不调模型）  
   - 动手时优先：复制 `apps/api/domains/_scaffold/` → `apps/api/domains/<你的名字>/`  
   - 需要工具示例时再对照：`apps/api/domains/demo_tools/`
   - 要看真实业务闭环时再参考：`apps/api/domains/work_order_ops/`（查询、图表、引用、审批；不是脚手架）

2. **改自己的目录**  
   至少会碰到：流程（`graph`）、工具（`tools`）、状态（`state`）、本目录注册（`bootstrap`）。

3. **登记到总表**  
   在 `apps/api/domains/bootstrap.py` 里（与现有 demo 保持一致）：
   - `import` 你的 bootstrap  
   - 在 `register_all` 里调用 `register(...)`  
   - 写入 `DOMAIN_META_MAP`（调试台展示说明会用到）

4. **权限**  
   工具若需要权限，照现有 demo 挂 `required_permissions`。  
   **当前调用方不具备的权限**所对应的工具，不要进模型可见的工具列表；  
   平台还会在真正调用时再鉴权一次（不要只依赖「列表里看不见」）。

5. **跑起来验收**  
   - 按 [快速开始](./02-quickstart.md) 起 API（改完插件后重启一次，让新注册生效）  
   - 调试台选你的 `route`，或用 curl 打 `/chat/stream`  
   - 看到有回复 / 有 `done` 即可

6. **补一条测试（建议）**  
   参考 `apps/api/tests/test_chat_stream.py`，给新 route 写一条冒烟，避免以后改坏自己不知道。

## 不要做的事

- 在 `packages/core` 里写死你的业务名（核心库要保持「不知道你是谁」）  
- 在业务流程里直接 `import` 某个数据库/HTTP 适配器实现（应走 Port；组装放在服务启动的 `lifespan`）  
- 把整份产品大编排一次性塞进一个插件（插件尽量只装**这一块业务**需要的东西）

## 下一步

- 逐步清单与约定：[add-a-domain.md](../add-a-domain.md)  
- 给助手用的检查清单：[ai-instructions/02-domain-development.md](../ai-instructions/02-domain-development.md)  
- 提示词开场（任意 AI 工具）：[ai-instructions/05-ai-coding.md](../ai-instructions/05-ai-coding.md)  
- 硬规则与分层：[AGENTS.md](../../AGENTS.md)、[architecture.md](../architecture.md)

---

← [基本概念](./03-concepts.md) · [文档目录](../INDEX.md) · 下一篇：[AI 控制台](./05-console.md) →
