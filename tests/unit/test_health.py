from fastapi.testclient import TestClient

from hamoon.app.api.routes import health as health_routes
from hamoon.app.config.settings import Settings, get_settings
from hamoon.app.main import app


def test_liveness() -> None:
    client = TestClient(app)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "alive"
    assert response.headers["X-Request-Id"]
    assert response.headers["X-Correlation-Id"]


def test_request_context_propagates_client_headers() -> None:
    client = TestClient(app)

    response = client.get(
        "/health/live",
        headers={
            "X-Request-Id": "req-test-1",
            "X-Correlation-Id": "corr-test-1",
        },
    )

    assert response.headers["X-Request-Id"] == "req-test-1"
    assert response.headers["X-Correlation-Id"] == "corr-test-1"


def test_release_identity_reports_build_and_migration_metadata(
    monkeypatch,
) -> None:
    async def migration_versions() -> tuple[str, ...]:
        return ("20261004_release_identity",)

    monkeypatch.setattr(
        health_routes,
        "database_migration_versions",
        migration_versions,
    )
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        application_version="1.2.3",
        git_commit="a" * 40,
        image_id="sha256:" + "b" * 64,
        deployment_id="test-deployment",
    )
    try:
        response = TestClient(app).get("/health/release")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["application_version"] == "1.2.3"
    assert payload["git_commit"] == "a" * 40
    assert payload["image_id"] == "sha256:" + "b" * 64
    assert payload["deployment_id"] == "test-deployment"
    assert payload["database_migration_versions"] == [
        "20261004_release_identity"
    ]
