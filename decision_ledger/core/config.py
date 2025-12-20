"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Imputable"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # API
    api_prefix: str = "/api/v1"
    allowed_origins: list[str] = Field(default=["http://localhost:3000"])

    # Database
    database_url: PostgresDsn = Field(
        default="postgresql://postgres:postgres@localhost:5432/imputable"
    )
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=100)
    database_echo: bool = False  # Log SQL queries

    # Authentication
    secret_key: str = Field(
        default="change-me-in-production-use-strong-random-key"
    )
    access_token_expire_minutes: int = Field(default=30, ge=5)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    # Security
    bcrypt_rounds: int = Field(default=12, ge=4, le=31)

    # Rate Limiting
    rate_limit_requests: int = Field(default=100, ge=1)
    rate_limit_period_seconds: int = Field(default=60, ge=1)

    # Audit
    audit_chain_enabled: bool = True  # Enable cryptographic chain
    audit_retention_days: int = Field(default=365 * 7, ge=30)  # 7 years

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL."""
        return str(self.database_url)

    @property
    def database_url_async(self) -> str:
        """Get async database URL (uses asyncpg)."""
        url = str(self.database_url)
        return url.replace("postgresql://", "postgresql+asyncpg://")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
