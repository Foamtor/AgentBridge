-- Operator-managed LLM connections. api_key_ciphertext is authenticated encrypted data.
CREATE TABLE IF NOT EXISTS bridge_model_configs (
    alias TEXT PRIMARY KEY,
    provider TEXT NOT NULL DEFAULT 'openai_compatible',
    api_base TEXT NOT NULL,
    model_name TEXT NOT NULL,
    api_key_ciphertext TEXT NOT NULL,
    temperature DOUBLE PRECISION NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT bridge_model_configs_alias_format
        CHECK (alias ~ '^[a-z][a-z0-9_-]{0,63}$'),
    CONSTRAINT bridge_model_configs_provider
        CHECK (provider = 'openai_compatible'),
    CONSTRAINT bridge_model_configs_temperature
        CHECK (temperature >= 0 AND temperature <= 2)
);
