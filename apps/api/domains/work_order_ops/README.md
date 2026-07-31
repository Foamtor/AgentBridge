# Work-order operations reference domain

`work_order_ops` is the P1 golden reference for converting a traditional
business workflow into an AI conversation. All bundled records are synthetic.
It demonstrates tenant-scoped lists, statistics, ECharts options, RAG
citations, an immutable approval draft, and atomic work-order plus ledger
creation.

## Setup

Apply migrations in order:

```powershell
psql $env:PG_DSN -f apps/api/migrations/004_approval_execution.sql
psql $env:PG_DSN -f apps/api/migrations/005_work_order_ops.sql
```

Use `APPROVAL_STORE_BACKEND=postgres` for P1 restart-safe acceptance.
`APPROVAL_STORE_BACKEND=memory` is only for CI and local demonstrations.
Configure `KNOWLEDGE_BACKEND=langchain_pg` for the real RAG path, or
`KNOWLEDGE_BACKEND=external` for a remote retrieval service.

For the read-only RAG-Agent reference backend, provide a read-only DSN through
the deployment environment and run the acceptance probe. Do not commit a DSN:

```powershell
$env:KNOWLEDGE_BACKEND='rag_agent_pg'
$env:RAG_AGENT_PG_DSN='provided by the secure local environment'
$env:RAG_AGENT_DEMO_TENANT='rag-agent-demo'
$env:RAG_AGENT_EMBED_API_BASE='http://127.0.0.1:8080/v1'
$env:RAG_AGENT_EMBED_MODEL='BAAI/bge-m3'
$env:RAG_AGENT_EMBED_DIMENSIONS='512'
python scripts/verify_rag_agent_readonly.py
```

Required permissions:

- `workorder:read`: list and statistics;
- `knowledge:read`: SOP/FAQ retrieval;
- both `workorder:create` and `workorder:assign`: draft and approved creation;
- `approval:decide`: approve or deny a pending action.

Example queries:

- `show work orders`
- `show work orders as a pie chart`
- `search the work-order SOP`
- `create work order`

The request uses the standard endpoint:

```json
{"query":"show work orders","thread_id":"demo-1","route":"work_order_ops"}
```

## Extension events

Every business payload has `schema_version: 1`.

```json
{"type":"x.work_order_ops.list","data":{"schema_version":1,"resource":"work_orders","columns":[{"key":"id","label":"id","data_type":"string"}],"rows":[],"total":0,"truncated":false}}
```

```json
{"type":"x.work_order_ops.chart","data":{"schema_version":1,"chart_type":"bar","x_axis":{"categories":["open"]},"series":[{"name":"工单数","data":[1]}],"echarts_option":{"xAxis":{"type":"category","data":["open"]},"series":[{"type":"bar","data":[1]}]}}}
```

`chart_type` supports `bar`, `line`, and `pie`. A client may pass
`echarts_option` directly to `setOption()`. If ECharts or the requested chart
type is unavailable, render the title, `x_axis.categories`, and `series.data`
as a value list.

```json
{"type":"x.work_order_ops.ledger_preview","data":{"schema_version":1,"draft_id":"draft-r1","work_order":{"title":"脱敏工单草稿","priority":"medium","assignee_id":"assignee-demo-a"},"ledger":{"summary":"待审核创建工单","source":"assistant"},"approval_required":true}}
```

```json
{"type":"x.bridge.approval_required","data":{"tool":"create_work_order","timeout_seconds":1800,"action":{"type":"work_order_ops.create_v1","payload":{"draft_id":"draft-r1","title":"脱敏工单草稿","priority":"medium","assignee_id":"assignee-demo-a","ledger_summary":"待审核创建工单"}}}}
```

Approve with `POST /approvals/{approval_id}` and
`{"decision":"approve"}`. Success produces:

```json
{"type":"x.work_order_ops.work_order_created","data":{"schema_version":1,"work_order_id":"WO-ap-1","ledger_id":"LG-ap-1","assignee_id":"assignee-demo-a","status":"open"}}
```

`approval_id` is the idempotency key. Repeating approval or recovering an
expired execution lease reconstructs the same result and does not insert a
second work order or ledger.
