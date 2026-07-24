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
    pg_database: str = "agent_base"
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
    fake_runtime: bool = Field(default=False, validation_alias="AGENT_BASE_FAKE_RUNTIME")
    hooks_backend: str = Field(default="noop", validation_alias="HOOKS_BACKEND")
    rate_limit_per_minute: int = Field(
        default=0, validation_alias="RATE_LIMIT_PER_MINUTE"
    )


def get_settings() -> Settings:
    return Settings()
