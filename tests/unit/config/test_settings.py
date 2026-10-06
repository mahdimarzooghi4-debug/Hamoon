import pytest
from pydantic import ValidationError

from hamoon.app.config.settings import Settings


def _production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "application_version": "0.1.0",
        "git_commit": "a" * 40,
        "image_id": "sha256:" + "b" * 64,
        "deployment_id": "hamoon-prod-20261004-001",
        "metrics_enabled": True,
        "metrics_access_token": "m" * 32,
        "otel_enabled": True,
        "otel_exporter_otlp_endpoint": "https://otel.internal/v1/traces",
        "otel_exporter_otlp_logs_endpoint": "https://otel.internal/v1/logs",
        "structured_logging": True,
        "database_url": (
            "postgresql+asyncpg://hamoon:strong-password@db.internal:5432/hamoon"
        ),
        "nats_url": "nats://nats.internal:4222",
        "temporal_address": "temporal.internal:7233",
        "oidc_issuer_url": "https://identity.example.com/realms/hamoon",
        "oidc_jwks_url": (
            "https://identity.example.com/realms/hamoon/"
            "protocol/openid-connect/certs"
        ),
        "evidence_storage_backend": "s3",
        "evidence_s3_endpoint": "https://objects.example.com",
        "evidence_s3_access_key": "production-access-key",
        "evidence_s3_secret_key": "production-secret-key-value",
        "evidence_scanner_backend": "http",
        "evidence_scanner_endpoint": "https://scanner.example.com/v1/scan",
        "evidence_scanner_token": "s" * 32,
        "evidence_signing_secret": "production-evidence-signing-secret-32-bytes",
        "internal_model_artifact_storage_backend": "s3",
        "internal_model_artifact_s3_endpoint": "https://models.example.com",
        "internal_model_artifact_s3_access_key": "model-artifact-access-key",
        "internal_model_artifact_s3_secret_key": (
            "model-artifact-production-secret"
        ),
        "internal_model_artifact_s3_bucket": "hamoon-model-artifacts",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_configuration_accepts_remote_secure_dependencies() -> None:
    settings = _production_settings()

    assert settings.environment == "production"
    assert settings.evidence_storage_backend == "s3"
    assert settings.internal_model_artifact_storage_backend == "s3"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        (
            "application_version",
            "",
            "PRODUCTION_APPLICATION_VERSION_REQUIRED",
        ),
        (
            "git_commit",
            "development",
            "PRODUCTION_GIT_COMMIT_REQUIRED",
        ),
        (
            "image_id",
            "local",
            "PRODUCTION_IMAGE_ID_REQUIRED",
        ),
        (
            "deployment_id",
            "local",
            "PRODUCTION_DEPLOYMENT_ID_REQUIRED",
        ),
        (
            "metrics_enabled",
            False,
            "PRODUCTION_METRICS_REQUIRED",
        ),
        (
            "metrics_access_token",
            "short",
            "PRODUCTION_METRICS_ACCESS_TOKEN_REQUIRED",
        ),
        (
            "otel_enabled",
            False,
            "PRODUCTION_OTEL_REQUIRED",
        ),
        (
            "otel_exporter_otlp_endpoint",
            "http://otel.internal/v1/traces",
            "PRODUCTION_OTEL_EXPORTER_HTTPS_REQUIRED",
        ),
        (
            "otel_exporter_otlp_logs_endpoint",
            "http://otel.internal/v1/logs",
            "PRODUCTION_OTEL_LOGS_EXPORTER_HTTPS_REQUIRED",
        ),
        (
            "structured_logging",
            False,
            "PRODUCTION_STRUCTURED_LOGGING_REQUIRED",
        ),
        (
            "openai_api_key",
            "external-provider-key",
            "PRODUCTION_EXTERNAL_AI_CREDENTIAL_FORBIDDEN",
        ),
        (
            "database_url",
            "postgresql+asyncpg://hamoon:hamoon@localhost:5432/hamoon",
            "PRODUCTION_DATABASE_ENDPOINT_INVALID",
        ),
        (
            "nats_url",
            "nats://127.0.0.1:4222",
            "PRODUCTION_NATS_ENDPOINT_INVALID",
        ),
        (
            "temporal_address",
            "localhost:7233",
            "PRODUCTION_TEMPORAL_ENDPOINT_INVALID",
        ),
        (
            "oidc_issuer_url",
            "http://identity.example.com/realms/hamoon",
            "PRODUCTION_OIDC_HTTPS_REQUIRED",
        ),
        (
            "oidc_jwks_url",
            "http://identity.example.com/realms/hamoon/certs",
            "PRODUCTION_OIDC_JWKS_HTTPS_REQUIRED",
        ),
        (
            "evidence_storage_backend",
            "local",
            "PRODUCTION_EVIDENCE_STORAGE_REQUIRED",
        ),
        (
            "evidence_s3_endpoint",
            "http://objects.example.com",
            "PRODUCTION_EVIDENCE_S3_HTTPS_REQUIRED",
        ),
        (
            "evidence_s3_access_key",
            "minio",
            "PRODUCTION_EVIDENCE_S3_CREDENTIALS_REQUIRED",
        ),
        (
            "evidence_s3_secret_key",
            "minio12345",
            "PRODUCTION_EVIDENCE_S3_CREDENTIALS_REQUIRED",
        ),
        (
            "evidence_signing_secret",
            "hamoon-local-evidence-secret",
            "PRODUCTION_EVIDENCE_SIGNING_SECRET_REQUIRED",
        ),
        (
            "internal_model_artifact_storage_backend",
            "local",
            "PRODUCTION_INTERNAL_MODEL_ARTIFACT_STORAGE_REQUIRED",
        ),
        (
            "internal_model_artifact_s3_endpoint",
            "http://models.example.com",
            "PRODUCTION_INTERNAL_MODEL_ARTIFACT_S3_HTTPS_REQUIRED",
        ),
        (
            "internal_model_artifact_s3_access_key",
            "minio",
            "PRODUCTION_INTERNAL_MODEL_ARTIFACT_S3_CREDENTIALS_REQUIRED",
        ),
        (
            "internal_model_artifact_s3_secret_key",
            "minio12345",
            "PRODUCTION_INTERNAL_MODEL_ARTIFACT_S3_CREDENTIALS_REQUIRED",
        ),
        (
            "evidence_scanner_backend",
            "local",
            "PRODUCTION_EVIDENCE_SCANNER_REQUIRED",
        ),
        (
            "evidence_scanner_endpoint",
            "http://scanner.example.com/v1/scan",
            "PRODUCTION_EVIDENCE_SCANNER_HTTPS_REQUIRED",
        ),
        (
            "evidence_scanner_token",
            "short",
            "PRODUCTION_EVIDENCE_SCANNER_TOKEN_REQUIRED",
        ),
    ],
)
def test_production_configuration_rejects_unsafe_values(
    field: str,
    value: object,
    code: str,
) -> None:
    with pytest.raises(ValidationError, match=code):
        _production_settings(**{field: value})


def test_local_configuration_keeps_developer_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "local"
    assert settings.evidence_storage_backend == "local"
    assert settings.internal_model_artifact_storage_backend == "local"


def test_unknown_evidence_storage_backend_is_rejected_in_all_environments() -> None:
    with pytest.raises(ValidationError, match="EVIDENCE_STORAGE_BACKEND_INVALID"):
        Settings(_env_file=None, evidence_storage_backend="filesystem-v2")



def test_unknown_evidence_scanner_backend_is_rejected_in_all_environments() -> None:
    with pytest.raises(ValidationError, match="EVIDENCE_SCANNER_BACKEND_INVALID"):
        Settings(_env_file=None, evidence_scanner_backend="magic")


def test_unknown_internal_model_artifact_storage_backend_is_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match="INTERNAL_MODEL_ARTIFACT_STORAGE_BACKEND_INVALID",
    ):
        Settings(
            _env_file=None,
            internal_model_artifact_storage_backend="database",
        )
