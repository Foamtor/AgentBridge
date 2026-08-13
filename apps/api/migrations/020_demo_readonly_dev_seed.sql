-- Synthetic orders for the default dev tenant. Used by the read-only plugin.
INSERT INTO demo_orders (id, tenant_id, status)
VALUES
    (1001, 'dev', 'open'),
    (1002, 'dev', 'open'),
    (1003, 'dev', 'closed')
ON CONFLICT (id) DO NOTHING;
