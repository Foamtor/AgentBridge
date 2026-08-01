-- Synthetic rag-agent-demo reference data. No PII or customer identifiers.
INSERT INTO assignees (id, tenant_id, name, team, active, specialties)
VALUES (
    'assignee-rag-demo',
    'rag-agent-demo',
    '演示处理员',
    '演示运营组',
    TRUE,
    'equipment'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO work_orders (
    id,
    tenant_id,
    approval_id,
    title,
    status,
    priority,
    assignee_id
)
VALUES (
    'WO-RAG-DEMO-001',
    'rag-agent-demo',
    'seed-rag-agent-demo',
    '演示设备巡检告警',
    'open',
    'medium',
    'assignee-rag-demo'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO ledgers (
    id,
    tenant_id,
    approval_id,
    work_order_id,
    summary
)
VALUES (
    'LG-RAG-DEMO-001',
    'rag-agent-demo',
    'seed-rag-agent-demo',
    'WO-RAG-DEMO-001',
    '演示设备告警已进入待处理队列'
)
ON CONFLICT (id) DO NOTHING;
