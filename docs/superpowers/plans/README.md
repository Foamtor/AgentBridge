# AgentBridge 实施计划索引

> 这是**历史实施记录**（当时怎么分期干活）。阅读时若遇到旧词，请对照根目录 README 的「先搞懂几个词」。  
> 产品总说明：[../../00-AgentBridge完整方案.md](../../00-AgentBridge完整方案.md)  
> 路线图：[../../roadmap.md](../../roadmap.md)  
> 依赖关系：[DEPENDENCIES.md](./DEPENDENCIES.md)

按依赖顺序做完即可。推荐用分任务执行的方式推进。

| 顺序 | 计划 | 文件 | 能力 | 版本含义 |
|------|------|------|------|----------|
| 1 | 可安全接入 | [plan1](./2026-07-24-plan1-secure-access.md) | M1+M2a+M2b | → v0.2 |
| 2 | 可查库 | [plan2](./2026-07-24-plan2-datasource.md) | M3 | → v0.3 |
| 3 | 单机可运维 | [plan3](./2026-07-24-plan3-single-node-prod.md) | M4 | → **v1.0** |
| 4 | 智能与治理 | [plan4](./2026-07-24-plan4-intelligence-governance.md) | M5–M7 | → v1.x |
| 5 | 协作与扩展 | [plan5](./2026-07-24-plan5-collaboration-scale.md) | M8–M10 | → 多机/v2.0 |

## 谁依赖谁

```text
M0 → Plan1(M2a) → Plan2 ─┐
         ↓                │
       Plan1(M2b) ────────┼→ Plan3 → Plan4 → Plan5
         ↑ 可与 Plan2 并行 ─┘         │
                                    └─ SDK 审批演示需要 Plan4 里审批相关任务
```

| 谁要用 | 必须先完成 | 可以暂缓 / 用假实现 |
|--------|------------|---------------------|
| Plan2 | Plan1 的身份与工具权限 | 可与 Plan1 的事件回放并行 |
| Plan3 | Plan1（至少请求流水线） | Plan2 可软依赖 |
| Plan4 | Plan1（含 Run 存储）+ Plan3 | Plan2 可软依赖 |
| Plan5 | Plan1；若演示审批还需 Plan4 审批任务 | Plan3/4 其余可软依赖 |

**下一步：** 按真实业务插件与部署需要使用已交付能力；多机见 [multi-instance.md](../../multi-instance.md)。
