from fastapi.testclient import TestClient

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
