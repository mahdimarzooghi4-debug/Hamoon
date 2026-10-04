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
    nats_events_stream: str = "HAMOON_EVENTS"
    outbox_batch_size: int = 50
    outbox_poll_seconds: float = 1.0
    outbox_lease_seconds: int = 30
    outbox_max_backoff_seconds: int = 300
    otel_enabled: bool = False
    otel_service_name: str = "hamoon-api"
    otel_exporter_otlp_endpoint: str | None = None
    metrics_enabled: bool = True
    structured_logging: bool = True

    evidence_storage_backend: str = "local"
    evidence_local_root: str = ".hamoon/evidence"
    evidence_s3_endpoint: str = "http://localhost:9000"
    evidence_s3_access_key: str = "minio"
    evidence_s3_secret_key: str = "minio12345"
    evidence_s3_bucket: str = "hamoon-evidence"
    evidence_s3_region: str = "us-east-1"
    evidence_s3_request_timeout_seconds: float = 10.0
    evidence_signing_secret: str = "hamoon-local-evidence-secret"
    evidence_upload_ttl_seconds: int = 300
    evidence_download_ttl_seconds: int = 300
    evidence_max_upload_bytes: int = 10 * 1024 * 1024
    evidence_allowed_media_types: str = (
        "application/pdf,image/jpeg,image/png,text/plain"
    )

    oidc_issuer_url: str = "http://localhost:8081/realms/hamoon-local"
    oidc_audience: str = "hamoon-api"
    oidc_jwks_url: str | None = None
    oidc_clock_skew_seconds: int = 30

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_seconds: float = 60.0

    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_core_task_queue: str = "hamoon-core"


@lru_cache
def get_settings() -> Settings:
    return Settings()
