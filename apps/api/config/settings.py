"""pydantic-settings for the API host."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    auth_required: bool = False
    auth_dev_stub: bool = Field(default=False, validation_alias="AUTH_DEV_STUB")
    pg_dsn: str = Field(default="", validation_alias="PG_DSN")
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "agentbridge"
    pg_user: str = "postgres"
    pg_password: str = "postgres"
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_jwt_secret: str = Field(default="", validation_alias="OIDC_JWT_SECRET")
    llm_api_key: str = ""
    use_memory_checkpointer: bool = True
    enable_data_source: bool = Field(
        default=False, validation_alias="ENABLE_DATA_SOURCE"
    )
    data_source_dsn: str = Field(default="", validation_alias="DATA_SOURCE_DSN")
    approval_store_backend: str = Field(
        default="memory", validation_alias="APPROVAL_STORE_BACKEND"
    )
    approval_execution_lease_seconds: float = Field(
        default=60.0, validation_alias="APPROVAL_EXECUTION_LEASE_SECONDS"
    )
    approval_expiry_scan_interval_seconds: float = Field(
        default=30.0,
        gt=0,
        validation_alias="APPROVAL_EXPIRY_SCAN_INTERVAL_SECONDS",
    )
    fake_runtime: bool = Field(default=False, validation_alias="AGENTBRIDGE_FAKE_RUNTIME")
    hooks_backend: str = Field(default="noop", validation_alias="HOOKS_BACKEND")
    rate_limit_per_minute: int = Field(
        default=0, validation_alias="RATE_LIMIT_PER_MINUTE"
    )
    otel_enabled: bool = Field(default=False, validation_alias="OTEL_ENABLED")
    llm_backend: str = Field(default="direct", validation_alias="LLM_BACKEND")
    lock_backend: str = Field(default="memory", validation_alias="LOCK_BACKEND")
    rate_limit_backend: str = Field(
        default="memory", validation_alias="RATE_LIMIT_BACKEND"
    )
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    policy_bundle_version: str = Field(
        default="role_policy/v1", validation_alias="POLICY_BUNDLE_VERSION"
    )
    policy_matrix_roles: str = Field(
        default="admin,viewer", validation_alias="POLICY_MATRIX_ROLES"
    )
    admin_tool_invoke_enabled: bool = Field(
        default=False, validation_alias="ADMIN_TOOL_INVOKE_ENABLED"
    )
    knowledge_backend: str = Field(default="fake", validation_alias="KNOWLEDGE_BACKEND")
    rag_agent_pg_dsn: str = Field(
        default="", validation_alias="RAG_AGENT_PG_DSN"
    )
    rag_agent_demo_tenant: str = Field(
        default="rag-agent-demo", validation_alias="RAG_AGENT_DEMO_TENANT"
    )
    rag_agent_embed_api_base: str = Field(
        default="http://127.0.0.1:8080/v1",
        validation_alias="RAG_AGENT_EMBED_API_BASE",
    )
    rag_agent_embed_api_key: str = Field(
        default="EMPTY", validation_alias="RAG_AGENT_EMBED_API_KEY"
    )
    rag_agent_embed_model: str = Field(
        default="BAAI/bge-m3", validation_alias="RAG_AGENT_EMBED_MODEL"
    )
    rag_agent_embed_dimensions: int = Field(
        default=512, validation_alias="RAG_AGENT_EMBED_DIMENSIONS"
    )
    kb_dsn: str = Field(default="", validation_alias="KB_DSN")
    embed_api_base: str = Field(default="", validation_alias="EMBED_API_BASE")
    embed_model: str = Field(default="", validation_alias="EMBED_MODEL")
    embed_dimensions: int = Field(default=0, validation_alias="EMBED_DIMENSIONS")
    embed_api_key: str = Field(default="", validation_alias="EMBED_API_KEY")
    kb_external_base_url: str = Field(default="", validation_alias="KB_EXTERNAL_BASE_URL")
    kb_external_api_key: str = Field(default="", validation_alias="KB_EXTERNAL_API_KEY")
    kb_external_timeout_seconds: float = Field(
        default=5.0, validation_alias="KB_EXTERNAL_TIMEOUT_SECONDS"
    )
    kb_external_failure_policy: str = Field(
        default="empty_hits", validation_alias="KB_EXTERNAL_FAILURE_POLICY"
    )


def get_settings() -> Settings:
    return Settings()
