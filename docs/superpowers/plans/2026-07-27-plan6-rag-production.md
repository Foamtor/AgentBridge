# Plan6 — 多知识后端（底座①）

> **状态：** 待实施（已按 [方案收敛](../specs/2026-07-27-scheme-convergence.md) 收窄）  
> **设计稿：** [../specs/2026-07-27-rag-production-design.md](../specs/2026-07-27-rag-production-design.md) · [R-A 切片设计](../specs/2026-07-27-platform-ra-design.md)  
> **R-A 详细实施计划：** [./2026-07-27-platform-ra.md](./2026-07-27-platform-ra.md)（优先按该文档执行 T1–T8）  
> **external 协议：** [../specs/2026-07-27-external-rag-protocol.md](../specs/2026-07-27-external-rag-protocol.md)  
> **归属：** [design-tracks.md](../../design-tracks.md) **① 底座**  
> **依赖：** Plan1–5；M7 Retriever + `demo_rag`  
> **版本目标：** v2.1  
> **R-A 钉死：** 只做 **`langchain_pg`**（不做并行 product）

---

## 总览

| 阶段 | 任务 | 里程碑 |
|------|------|--------|
| **R-A** | T1–T8 | Port + **LangchainPgRetriever** + 租户 + demo_rag |
| **R-B** | T9–T14 | KnowledgeIngest + `/ingest` + 任务 |
| **R-C** | T15–T20 | **external**（按协议）+ 观测评测；**可选** product / mem0 |

可与 [Plan7](./2026-07-27-plan7-ai-console-c0.md) 并行。

---

## R-A（仅 langchain_pg）

### T1 — Port 扩展（含统一 KnowledgeHit 字段）

### T2 — `rag` / `rag-langchain` extra

### T3 — `LangchainPgRetriever` 适配器 + 租户强制

### T4 — lifespan：`KNOWLEDGE_BACKEND=fake|langchain_pg`（此阶段不接 product/external）

### T5 — 架构门禁（domains 禁 import langchain_postgres）

### T6 — 升级 demo_rag

### T7 — 文档（knowledge-base / deploy）

### T8 — R-A 门禁

---

## R-B

### T9–T14 — 同前：Ingest Port、入库、`/ingest`、worker、门禁  

（仅要求 **langchain_pg** 路径闭环）

---

## R-C

### T15 — 按协议实现 `ExternalRagAdapter` + Mock 测

### T16 — （可选）`product` 适配器启动  

### T17 — citation 增强 / 只读文档 API（可选）

### T18 — 观测 + `run_kb_evals.py`

### T19 — mem0（可选）

### T20 — M11 总验收

---

## 纪律

1. **R-A 禁止**同时主攻 `product`。  
2. 业务插件只认 Port。  
3. external 必须以协议文档为准。  
4. 分析报告不在本 Plan。  
5. 控制台知识面板属 Plan7/C4。  
