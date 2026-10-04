import pytest
from pydantic import ValidationError

from hamoon.app.config.settings import Settings


def _production_settings(**overrides: str) -> Settings:
    values: dict[str, str] = {
        "environment": "production",
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
        "evidence_signing_secret": "production-evidence-signing-secret-32-bytes",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_configuration_accepts_remote_secure_dependencies() -> None:
    settings = _production_settings()

    assert settings.environment == "production"
    assert settings.evidence_storage_backend == "s3"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
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
    ],
)
def test_production_configuration_rejects_unsafe_values(
    field: str,
    value: str,
    code: str,
) -> None:
    with pytest.raises(ValidationError, match=code):
        _production_settings(**{field: value})


def test_local_configuration_keeps_developer_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "local"
    assert settings.evidence_storage_backend == "local"


def test_unknown_evidence_storage_backend_is_rejected_in_all_environments() -> None:
    with pytest.raises(ValidationError, match="EVIDENCE_STORAGE_BACKEND_INVALID"):
        Settings(_env_file=None, evidence_storage_backend="filesystem-v2")
