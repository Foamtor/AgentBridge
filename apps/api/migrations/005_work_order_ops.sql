-- Tenant-scoped synthetic reference data. No real customer data.
CREATE TABLE IF NOT EXISTS work_orders (id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, approval_id TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL, priority TEXT NOT NULL, assignee_id TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE (tenant_id, approval_id));
CREATE TABLE IF NOT EXISTS assignees (id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL, team TEXT NOT NULL, active BOOLEAN NOT NULL, specialties TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledgers (id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, approval_id TEXT NOT NULL, work_order_id TEXT NOT NULL, summary TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE (tenant_id, approval_id));
INSERT INTO assignees (id, tenant_id, name, team, active, specialties) VALUES ('assignee-demo-a', 'acme', '处理员-A', '运营组', TRUE, 'network'), ('assignee-demo-b', 'other', '处理员-B', '支持组', TRUE, 'database') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_orders (
    id, tenant_id, approval_id, title, status, priority, assignee_id
) VALUES
    ('WO-DEMO-A', 'acme', 'seed-acme', '脱敏网络告警', 'open', 'high', 'assignee-demo-a'),
    ('WO-DEMO-B', 'other', 'seed-other', '脱敏数据库告警', 'closed', 'medium', 'assignee-demo-b')
ON CONFLICT (id) DO NOTHING;
INSERT INTO ledgers (
    id, tenant_id, approval_id, work_order_id, summary
) VALUES
    ('LG-DEMO-A', 'acme', 'seed-acme', 'WO-DEMO-A', '脱敏示例台账'),
    ('LG-DEMO-B', 'other', 'seed-other', 'WO-DEMO-B', '脱敏示例台账')
ON CONFLICT (id) DO NOTHING;
