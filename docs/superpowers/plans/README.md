# AgentBridge 实施计划索引

> **当前执行入口：** [v0.1.0 首次开源发布计划](./2026-08-01-p3a-open-source-release-preparation.md)。
>
> 除明确标记“当前”的文件外，本目录是**历史分期怎么干活**的记录，不得从旧编号继续执行。
>
> 新人请先看：[文档目录](../../INDEX.md) → [guide 快速开始](../../guide/02-quickstart.md)。  
> 产品约定以 [完整方案](../../00-AgentBridge完整方案.md) 为准；与下文冲突时以完整方案为准。

> 阅读时若遇到旧词，请对照根目录 README。  
> 路线图：[../../roadmap.md](../../roadmap.md)  
> 依赖关系：[DEPENDENCIES.md](./DEPENDENCIES.md)

下表保留历史依赖关系以便追溯；当前工作只按“当前”行所链接的 Spec/Plan 推进。

| 顺序 | 计划 | 文件 | 能力 | 版本含义 |
|------|------|------|------|----------|
| 1 | 可安全接入 | [plan1](./2026-07-24-plan1-secure-access.md) | M1+M2a+M2b | → v0.2 |
| 2 | 可查库 | [plan2](./2026-07-24-plan2-datasource.md) | M3 | → v0.3 |
| 3 | 单机可运维 | [plan3](./2026-07-24-plan3-single-node-prod.md) | M4 | → **v1.0** |
| 4 | 智能与治理 | [plan4](./2026-07-24-plan4-intelligence-governance.md) | M5–M7 | → v1.x |
| 5 | 协作与扩展 | [plan5](./2026-07-24-plan5-collaboration-scale.md) | M8–M10 | → 多机/v2.0 |
| **6** | **① 多知识后端** | [plan6](./2026-07-27-plan6-rag-production.md) · **[R-A 详单](./2026-07-27-platform-ra.md)** | **M11** | → **v2.1** |
| **7** | **② AI 控制台 C0** | [plan7](./2026-07-27-plan7-ai-console-c0.md) | **M12** | 与 6 可并行 |
| — | 文档 P1 门面 | [docs-p1](./2026-07-28-docs-p1-gate.md) | 人类 guide | 文档 |
| — | P2-A 运行、安全、RAG、控制台验证 | [p2-a](./2026-08-01-p2a-runtime-security-rag-console-validation.md) | 发布 P2-A | 已完成；部署/多机留给 P2-B |
| **当前** | **v0.1.0 首次开源发布** | **[active plan](./2026-08-01-p3a-open-source-release-preparation.md)** | 双语首页、AI 读仓、黄金案例、全栈 Compose | 已复核，待实施；不做公共包发布 |
| — | 全面审阅记录 | [full-review](./2026-07-28-full-review.md) | 代码+文档抽查 | 文档 |

> 三类划分说明见入门文：[为什么用它 · 三块东西](../../guide/01-why.md)  
> 设计稿：[底座最终形态](../specs/2026-07-27-platform-final-spec.md)、[AI 控制台](../specs/2026-07-27-ai-admin-console-design.md)、[管理后端](../specs/2026-07-27-admin-backend-final-spec.md)

## 谁依赖谁

```text
M0 → Plan1(M2a) → Plan2 ─┐
         ↓                │
       Plan1(M2b) ────────┼→ Plan3 → Plan4 → Plan5
         ↑ 可与 Plan2 并行 ─┘         │
                                    ├→ Plan6（① 知识后端）
                                    └→ Plan7（② 控制台 C0，可与 Plan6 并行）
③ 业务插件：按项目单独立项，硬依赖 Plan1；软依赖 Plan6（若需真检索）
```

| 谁要用 | 必须先完成 | 可以暂缓 / 用假实现 |
|--------|------------|---------------------|
| Plan2 | Plan1 的身份与工具权限 | 可与 Plan1 的事件回放并行 |
| Plan3 | Plan1（至少请求流水线） | Plan2 可软依赖 |
| Plan4 | Plan1（含 Run 存储）+ Plan3 | Plan2 可软依赖 |
| Plan5 | Plan1；若演示审批还需 Plan4 审批任务 | Plan3/4 其余可软依赖 |
| **Plan6** | **Plan1–5；M7 Retriever（硬）** | external/product 可分期；MinerU 软 |
| **Plan7** | **Plan1–5（admin/调试台）** | **不硬依赖 Plan6** |

**下一步：** 执行表中“当前”计划；新人入口见 [文档目录](../../INDEX.md)。
