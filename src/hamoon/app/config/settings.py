from functools import lru_cache
from pathlib import Path
import re
from typing import Self
from urllib.parse import urlsplit

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1", "::"})
_GIT_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-fA-F]{64}$")
_DEPLOYMENT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _endpoint_host(value: str) -> str | None:
    candidate = value.strip()
    if not candidate:
        return None
    parsed = urlsplit(candidate if "://" in candidate else f"//{candidate}")
    return parsed.hostname.lower() if parsed.hostname is not None else None


def _is_local_host(host: str | None) -> bool:
    if host is None:
        return True
    return host in _LOCAL_HOSTS or host.endswith(".localhost")


def _is_remote_endpoint(value: str) -> bool:
    return not _is_local_host(_endpoint_host(value))


def _is_remote_https(value: str) -> bool:
    parsed = urlsplit(value.strip())
    return parsed.scheme == "https" and not _is_local_host(parsed.hostname)


class Settings(BaseSettings):
    """Typed runtime configuration for Hamoon."""

    model_config = SettingsConfigDict(
        env_prefix="HAMOON_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Hamoon"
    application_version: str = "0.1.0"
    git_commit: str = "development"
    image_id: str = "local"
    deployment_id: str = "local"
    environment: str = "local"
    database_url: str = "postgresql+asyncpg://hamoon:hamoon@localhost:5432/hamoon"
    nats_url: str = "nats://localhost:4222"
    nats_events_stream: str = "HAMOON_EVENTS"
    outbox_batch_size: int = 50
    outbox_poll_seconds: float = 1.0
    outbox_lease_seconds: int = 30
    outbox_max_backoff_seconds: int = 300
    provider_dispatch_config: SecretStr | None = None
    provider_dispatch_timeout_seconds: float = 10.0
    otel_enabled: bool = False
    otel_service_name: str = "hamoon-api"
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_logs_endpoint: str | None = None
    otel_exporter_otlp_headers: SecretStr | None = None
    metrics_enabled: bool = True
    metrics_access_token: SecretStr | None = None
    structured_logging: bool = True

    evidence_storage_backend: str = "local"
    evidence_local_root: str = ".hamoon/evidence"
    evidence_s3_endpoint: str = "http://localhost:9000"
    evidence_s3_access_key: str = "minio"
    evidence_s3_secret_key: str = "minio12345"
    evidence_s3_bucket: str = "hamoon-evidence"
    evidence_s3_region: str = "us-east-1"
    evidence_s3_request_timeout_seconds: float = 10.0
    evidence_scanner_backend: str = "local"
    evidence_scanner_endpoint: str | None = None
    evidence_scanner_token: SecretStr | None = None
    evidence_scanner_timeout_seconds: float = 20.0
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

    # Legacy environment trap only: Production rejects HAMOON_OPENAI_API_KEY.
    openai_api_key: str | None = None
    ai_model_root: str = ".hamoon/models"

    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_core_task_queue: str = "hamoon-core"
    temporal_provider_task_queue: str = "hamoon-provider"

    @model_validator(mode="after")
    def validate_runtime_safety(self) -> Self:
        backend = self.evidence_storage_backend.strip().lower()
        if backend not in {"local", "s3"}:
            raise ValueError("EVIDENCE_STORAGE_BACKEND_INVALID")
        scanner_backend = self.evidence_scanner_backend.strip().lower()
        if scanner_backend not in {"local", "http"}:
            raise ValueError("EVIDENCE_SCANNER_BACKEND_INVALID")
        if self.evidence_scanner_timeout_seconds <= 0:
            raise ValueError("EVIDENCE_SCANNER_TIMEOUT_INVALID")

        environment = self.environment.strip().lower()
        if environment not in {"prod", "production"}:
            return self

        errors: list[str] = []

        if not self.application_version.strip():
            errors.append("PRODUCTION_APPLICATION_VERSION_REQUIRED")
        if _GIT_COMMIT_RE.fullmatch(self.git_commit.strip()) is None:
            errors.append("PRODUCTION_GIT_COMMIT_REQUIRED")
        if _IMAGE_ID_RE.fullmatch(self.image_id.strip()) is None:
            errors.append("PRODUCTION_IMAGE_ID_REQUIRED")
        if (
            self.deployment_id.strip().lower()
            in {"", "local", "development", "unknown"}
            or _DEPLOYMENT_ID_RE.fullmatch(self.deployment_id.strip()) is None
        ):
            errors.append("PRODUCTION_DEPLOYMENT_ID_REQUIRED")

        if not self.metrics_enabled:
            errors.append("PRODUCTION_METRICS_REQUIRED")
        metrics_token = (
            self.metrics_access_token.get_secret_value().strip()
            if self.metrics_access_token is not None
            else ""
        )
        if len(metrics_token) < 32:
            errors.append("PRODUCTION_METRICS_ACCESS_TOKEN_REQUIRED")
        if not self.otel_enabled:
            errors.append("PRODUCTION_OTEL_REQUIRED")
        if (
            self.otel_exporter_otlp_endpoint is None
            or not _is_remote_https(self.otel_exporter_otlp_endpoint)
        ):
            errors.append("PRODUCTION_OTEL_EXPORTER_HTTPS_REQUIRED")

        if (
            self.otel_exporter_otlp_logs_endpoint is None
            or not _is_remote_https(self.otel_exporter_otlp_logs_endpoint)
        ):
            errors.append("PRODUCTION_OTEL_LOGS_EXPORTER_HTTPS_REQUIRED")
        if not self.structured_logging:
            errors.append("PRODUCTION_STRUCTURED_LOGGING_REQUIRED")

        if self.openai_api_key:
            errors.append("PRODUCTION_EXTERNAL_AI_CREDENTIAL_FORBIDDEN")
        model_root = Path(self.ai_model_root)
        if (
            not model_root.is_absolute()
            or str(model_root) in {"/", "/tmp", "/var/tmp"}
        ):
            errors.append("PRODUCTION_AI_MODEL_ROOT_REQUIRED")

        if not self.database_url.startswith("postgresql"):
            errors.append("PRODUCTION_POSTGRESQL_REQUIRED")
        if not _is_remote_endpoint(self.database_url):
            errors.append("PRODUCTION_DATABASE_ENDPOINT_INVALID")
        if not _is_remote_endpoint(self.nats_url):
            errors.append("PRODUCTION_NATS_ENDPOINT_INVALID")
        if not _is_remote_endpoint(self.temporal_address):
            errors.append("PRODUCTION_TEMPORAL_ENDPOINT_INVALID")

        if not _is_remote_https(self.oidc_issuer_url):
            errors.append("PRODUCTION_OIDC_HTTPS_REQUIRED")
        if self.oidc_jwks_url is not None and not _is_remote_https(self.oidc_jwks_url):
            errors.append("PRODUCTION_OIDC_JWKS_HTTPS_REQUIRED")

        if backend != "s3":
            errors.append("PRODUCTION_EVIDENCE_STORAGE_REQUIRED")
        if not _is_remote_https(self.evidence_s3_endpoint):
            errors.append("PRODUCTION_EVIDENCE_S3_HTTPS_REQUIRED")
        if (
            not self.evidence_s3_access_key.strip()
            or self.evidence_s3_access_key == "minio"
            or len(self.evidence_s3_secret_key) < 16
            or self.evidence_s3_secret_key == "minio12345"
        ):
            errors.append("PRODUCTION_EVIDENCE_S3_CREDENTIALS_REQUIRED")
        if (
            len(self.evidence_signing_secret) < 32
            or self.evidence_signing_secret == "hamoon-local-evidence-secret"
        ):
            errors.append("PRODUCTION_EVIDENCE_SIGNING_SECRET_REQUIRED")
        if scanner_backend != "http":
            errors.append("PRODUCTION_EVIDENCE_SCANNER_REQUIRED")
        if (
            self.evidence_scanner_endpoint is None
            or not _is_remote_https(self.evidence_scanner_endpoint)
        ):
            errors.append("PRODUCTION_EVIDENCE_SCANNER_HTTPS_REQUIRED")
        scanner_token = (
            self.evidence_scanner_token.get_secret_value().strip()
            if self.evidence_scanner_token is not None
            else ""
        )
        if len(scanner_token) < 32:
            errors.append("PRODUCTION_EVIDENCE_SCANNER_TOKEN_REQUIRED")

        if errors:
            raise ValueError("PRODUCTION_CONFIGURATION_INVALID:" + ",".join(errors))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
