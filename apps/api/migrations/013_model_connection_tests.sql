ALTER TABLE bridge_model_configs
    ADD COLUMN IF NOT EXISTS last_test_status TEXT,
    ADD COLUMN IF NOT EXISTS last_tested_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_test_latency_ms INTEGER,
    ADD COLUMN IF NOT EXISTS last_test_error TEXT;
