-- v0.1.0 default Compose demo data. All rows are synthetic and redacted.
INSERT INTO assignees (id, tenant_id, name, team, active, specialties)
VALUES
    ('assignee-dev-a', 'dev', 'Demo Operator A', 'Operations', TRUE, 'network'),
    ('assignee-dev-b', 'dev', 'Demo Operator B', 'Support', TRUE, 'equipment')
ON CONFLICT (id) DO NOTHING;

INSERT INTO work_orders (id, tenant_id, approval_id, title, status, priority, assignee_id)
VALUES
    ('WO-DEV-001', 'dev', 'seed-dev-001', 'Synthetic network alert', 'open', 'high', 'assignee-dev-a'),
    ('WO-DEV-002', 'dev', 'seed-dev-002', 'Synthetic equipment inspection', 'open', 'medium', 'assignee-dev-b'),
    ('WO-DEV-003', 'dev', 'seed-dev-003', 'Synthetic service follow-up', 'closed', 'low', 'assignee-dev-a')
ON CONFLICT (id) DO NOTHING;

INSERT INTO ledgers (id, tenant_id, approval_id, work_order_id, summary)
VALUES
    ('LG-DEV-001', 'dev', 'seed-dev-001', 'WO-DEV-001', 'Synthetic demo ledger: network alert'),
    ('LG-DEV-002', 'dev', 'seed-dev-002', 'WO-DEV-002', 'Synthetic demo ledger: equipment inspection')
ON CONFLICT (id) DO NOTHING;
