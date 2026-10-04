from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

from hamoon.app.observability.request_context import (
    current_correlation_id,
    current_request_id,
)

_SAFE_EXTRA_FIELDS = (
    "service",
    "environment",
    "operation",
    "error_code",
    "aggregate_type",
    "aggregate_id",
    "event_id",
    "workflow_id",
    "task_class",
    "provider_id",
    "model_alias",
    "formula_version",
    "event_type",
    "attempt_count",
)
_SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[^\s,;]+"),
    re.compile(
        r"(?i)(access_token|refresh_token|client_secret|password|national_id|phone)"
        r"([=:]\s*)[^\s,;]+"
    ),
)


def sanitize_log_message(value: str) -> str:
    sanitized = value
    for pattern in _SECRET_PATTERNS:
        if pattern.pattern.lower().startswith("(?i)(bearer"):
            sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
        else:
            sanitized = pattern.sub(r"\1\2[REDACTED]", sanitized)
    return sanitized


def build_safe_log_payload(
    record: logging.LogRecord,
    *,
    service_name: str = "hamoon",
    environment: str = "unknown",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": record.levelname,
        "logger": record.name,
        "service": service_name,
        "environment": environment,
        "message": sanitize_log_message(record.getMessage()),
    }
    request_id = current_request_id()
    correlation_id = current_correlation_id()
    if request_id is not None:
        payload["request_id"] = request_id
    if correlation_id is not None:
        payload["correlation_id"] = correlation_id

    for key in _SAFE_EXTRA_FIELDS:
        value = getattr(record, key, None)
        if value is not None:
            payload[key] = value

    if record.exc_info is not None:
        exc_type = record.exc_info[0]
        if exc_type is not None:
            payload["exception_type"] = exc_type.__name__
    return payload


class SafeJsonFormatter(logging.Formatter):
    def __init__(
        self,
        *,
        service_name: str = "hamoon",
        environment: str = "unknown",
    ) -> None:
        super().__init__()
        self._service_name = service_name
        self._environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload = build_safe_log_payload(
            record,
            service_name=self._service_name,
            environment=self._environment,
        )
        return json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            default=str,
        )


def configure_structured_logging(
    *,
    service_name: str,
    environment: str,
) -> None:
    root = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(
        SafeJsonFormatter(
            service_name=service_name,
            environment=environment,
        )
    )
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    logging.getLogger("hamoon").setLevel(logging.INFO)
    logging.LoggerAdapter(
        logging.getLogger("hamoon.bootstrap"),
        {"service": service_name, "environment": environment},
    ).info("Structured logging configured")
