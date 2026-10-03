from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed runtime configuration for Hamoon."""

    model_config = SettingsConfigDict(
        env_prefix="HAMOON_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Hamoon"
    environment: str = "local"
    database_url: str = "postgresql+asyncpg://hamoon:hamoon@localhost:5432/hamoon"
    nats_url: str = "nats://localhost:4222"
    otel_enabled: bool = False

    oidc_issuer_url: str = "http://localhost:8081/realms/hamoon-local"
    oidc_audience: str = "hamoon-api"
    oidc_jwks_url: str | None = None
    oidc_clock_skew_seconds: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
