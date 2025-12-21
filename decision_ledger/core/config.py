"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # This ensures env vars override defaults
        env_nested_delimiter="__",
    )

    # Application
    app_name: str = "Imputable"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # API
    api_prefix: str = "/api/v1"
    allowed_origins_str: str = Field(
        default="http://localhost:3000,http://localhost:3001,https://imputable.vercel.app",
        alias="ALLOWED_ORIGINS"
    )

    @property
    def allowed_origins(self) -> list[str]:
        """Parse allowed origins from string."""
        origins = self.allowed_origins_str
        if origins.startswith("["):
            import json
            try:
                return json.loads(origins)
            except:
                pass
        return [o.strip() for o in origins.split(",") if o.strip()]

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

    # Clerk Authentication
    clerk_secret_key: str | None = Field(default=None, alias="CLERK_SECRET_KEY")
    clerk_publishable_key: str | None = Field(default=None, alias="CLERK_PUBLISHABLE_KEY")
    clerk_jwks_url: str | None = Field(default=None)

    @property
    def clerk_enabled(self) -> bool:
        """Check if Clerk authentication is configured."""
        return bool(self.clerk_secret_key)

    @property
    def clerk_issuer(self) -> str | None:
        """Get Clerk issuer URL from publishable key."""
        if not self.clerk_publishable_key:
            return None
        # Extract instance ID from publishable key (pk_test_xxx or pk_live_xxx)
        # The key format is pk_{env}_{base64_encoded_frontend_api}
        try:
            import base64
            parts = self.clerk_publishable_key.split("_")
            if len(parts) >= 3:
                encoded = parts[2]
                # Add padding if needed
                padding = 4 - len(encoded) % 4
                if padding != 4:
                    encoded += "=" * padding
                frontend_api = base64.b64decode(encoded).decode("utf-8")
                # Remove any trailing $ or other non-domain characters
                frontend_api = frontend_api.rstrip("$").strip()
                return f"https://{frontend_api}"
        except Exception:
            pass
        return None

    # Security
    bcrypt_rounds: int = Field(default=12, ge=4, le=31)

    # Rate Limiting
    rate_limit_requests: int = Field(default=100, ge=1)
    rate_limit_period_seconds: int = Field(default=60, ge=1)

    # Audit
    audit_chain_enabled: bool = True  # Enable cryptographic chain
    audit_retention_days: int = Field(default=365 * 7, ge=30)  # 7 years

    # Stripe (Billing)
    stripe_secret_key: str | None = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str | None = Field(default=None, alias="STRIPE_WEBHOOK_SECRET")

    @property
    def stripe_enabled(self) -> bool:
        """Check if Stripe billing is configured."""
        return bool(self.stripe_secret_key)

    # Slack Integration
    slack_client_id: str | None = Field(default=None, alias="SLACK_CLIENT_ID")
    slack_client_secret: str | None = Field(default=None, alias="SLACK_CLIENT_SECRET")
    slack_signing_secret: str | None = Field(default=None, alias="SLACK_SIGNING_SECRET")
    slack_redirect_uri: str | None = Field(default=None, alias="SLACK_REDIRECT_URI")

    # Frontend URL (for OAuth redirects)
    frontend_url: str = Field(
        default="https://imputable.vercel.app",
        alias="FRONTEND_URL"
    )

    @property
    def slack_enabled(self) -> bool:
        """Check if Slack integration is configured."""
        return bool(self.slack_client_id and self.slack_client_secret)

    # Encryption key for storing sensitive tokens
    encryption_key: str | None = Field(
        default=None,
        alias="ENCRYPTION_KEY",
        description="Fernet key for encrypting Slack tokens. Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
    )

    @property
    def encryption_enabled(self) -> bool:
        """Check if encryption is configured."""
        return bool(self.encryption_key)

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
