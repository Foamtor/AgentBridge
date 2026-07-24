# 路线图（AgentBridge）

> 与 [00-AgentBridge完整方案.md](./00-AgentBridge完整方案.md) **v4.1.1** 对齐。  
> **不计人天**：能力里程碑 + 验收演示。细节契约以完整方案 §4 为准。  
> 实施计划（Plan r3）与依赖：[superpowers/plans/README.md](./superpowers/plans/README.md) · [DEPENDENCIES.md](./superpowers/plans/DEPENDENCIES.md)

## 实施计划（工程拆分）

不计人天后的能力里程碑，按 5 个可交付 Plan 施工（详见 [`docs/superpowers/plans/README.md`](./superpowers/plans/README.md)）：

| Plan | 里程碑 | 目标版本 |
|------|--------|----------|
| [Plan1 可安全接入](./superpowers/plans/2026-07-24-plan1-secure-access.md) | M1+M2a+M2b | v0.2 |
| [Plan2 可查库](./superpowers/plans/2026-07-24-plan2-datasource.md) | M3 | v0.3 |
| [Plan3 单机生产](./superpowers/plans/2026-07-24-plan3-single-node-prod.md) | M4 | **v1.0** |
| [Plan4 智能与治理](./superpowers/plans/2026-07-24-plan4-intelligence-governance.md) | M5–M7 | v1.x |
| [Plan5 协作与扩展](./superpowers/plans/2026-07-24-plan5-collaboration-scale.md) | M8–M10 | 多机 / v2.0 |

---

## 里程碑总览

| 里程碑 | 主题 | 状态 |
|--------|------|------|
| **M0** | 编排底座 | ✅ 已有 |
| **M1** | 开源包装 + AI 友好 | ✅ Plan1 |
| **M2a** | 身份 + Tool Policy（list+invoke 双检）+ 审计 + Pipeline | ✅ Plan1 |
| **M2b** | EventLog（全量已提交）+ 投影（delta 合并）+ replay | ✅ Plan1 |
| **M3** | DataSource + demo_readonly | ✅ Plan2 |
| **M4** | 单机生产面（ready/metrics/限流/OTel） | ✅ Plan3 |
| **M5** | Gateway（direct\|gateway 过渡）+ ContextManager + Prompt | 规划 |
| **M6** | DataFilter、双轨脱敏、Approval（释放锁/同 run resume） | 规划 |
| **M7** | Memory extra、RAG、citation | 规划 |
| **M8** | 多 Agent（单流 agent_id）、TS SDK、管理 API 鉴权 | 规划 |
| **M9** | 多机（Redis 锁/限流） | 规划 |
| **M10** | Eval、策略包版本、合规导出 | 规划 |

## 验收演示

| 里程碑 | 必须现场可演示 |
|--------|----------------|
| M0 | echo / demo_tools；409；cancel |
| M1 | scaffold → 对话；指令路径 CI |
| M2a | 两角色 tool 矩阵；**invoke deny 可测**；审计有记录 |
| M2b | `/threads/{id}/messages` 有上一轮；`replay` 与**已提交**事件一致；append 失败不推业务事件 |
| M3 | 权限下查库；无权限不进 list 且 invoke 拒绝 |
| M4 | `/ready`、`/metrics`；限流错误码；**InputValidator 400**；OTel 关联 `run_id` |
| M5 | `LLM_BACKEND=gateway` 换模型不改域；历史裁剪可测 |
| M6 | 审批等待期间锁释放；超时 deny；resume 同 `run_id`；脱敏用例；无规则 → 无数据 |
| M7 | ingest + citation；跨租户检索失败 |
| M8 | 单流多 `agent_id`；SDK 一轮含审批；admin 无权限 403 |
| M9 | 双实例同 thread 互斥；限流跨实例 |
| M10 | Eval CI；策略回滚；审计导出 |

## 用户旅程

| 旅程 | 里程碑 |
|------|--------|
| L1 | M0–M1 |
| L2 | M2a–M3 |
| L3 | M2（审计）+ M4（生产面） |
| 审批 / RAG / 多 Agent·SDK | M6 / M7 / M8 |
| 多机 | M9 |

## 对外版本（写死）

| 标签 | 含义 |
|------|------|
| v0.1 | M0–M1 |
| v0.2 | +M2a +M2b |
| v0.3 | +M3 |
| v0.4 | +M4 |
| **v1.0** | **= M0–M4 全部通过**（单机主承诺）；**不**要求 M5+ |
| v1.x | 叠加已交付的 M5–M8 |
| v1.x（多机） | +M9 |
| v2.0 | +M10 |

## 非目标

官方云托管 / Studio 产品化；研究型 GroupChat；替代企业 IAM。  
见完整方案 §1.2、附录 B。
