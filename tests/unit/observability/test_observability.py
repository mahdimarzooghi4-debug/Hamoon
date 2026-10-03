import json
import logging

from fastapi.testclient import TestClient

from hamoon.app.main import create_app
from hamoon.app.observability.json_logging import (
    SafeJsonFormatter,
    sanitize_log_message,
)


def test_log_sanitizer_redacts_tokens_and_sensitive_fields() -> None:
    message = (
        "Authorization=Bearer secret-token "
        "access_token=abc password=hunter2 phone=09120000000"
    )
    sanitized = sanitize_log_message(message)
    assert "secret-token" not in sanitized
    assert "abc" not in sanitized
    assert "hunter2" not in sanitized
    assert "09120000000" not in sanitized
    assert sanitized.count("[REDACTED]") == 4


def test_json_formatter_emits_only_safe_structured_extra() -> None:
    record = logging.LogRecord(
        name="hamoon.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="operation completed",
        args=(),
        exc_info=None,
    )
    record.event_id = "event-1"
    record.access_token = "must-not-leak"
    payload = json.loads(SafeJsonFormatter().format(record))

    assert payload["message"] == "operation completed"
    assert payload["event_id"] == "event-1"
    assert "access_token" not in payload


def test_metrics_endpoint_exposes_low_cardinality_http_metrics() -> None:
    client = TestClient(create_app())
    response = client.get("/health/live")
    assert response.status_code == 200

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "hamoon_http_requests_total" in metrics.text
    assert 'route="/health/live"' in metrics.text
    assert "X-Request-Id" in response.headers
