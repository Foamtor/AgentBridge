ALTER TABLE bridge_model_configs
    ADD COLUMN IF NOT EXISTS last_test_capability TEXT;
