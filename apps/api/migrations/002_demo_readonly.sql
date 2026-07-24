CREATE TABLE IF NOT EXISTS demo_orders (
  id int PRIMARY KEY,
  tenant_id text NOT NULL,
  status text NOT NULL
);
