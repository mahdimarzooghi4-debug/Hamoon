from __future__ import annotations

import logging
from collections.abc import Mapping

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry._logs import get_logger, set_logger_provider
from opentelemetry.context import get_current
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import (  # pyright: ignore[reportMissingTypeStubs]
    SQLAlchemyInstrumentor,
)
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy.ext.asyncio import AsyncEngine

from hamoon.app.config.settings import Settings
from hamoon.app.observability.json_logging import build_safe_log_payload

_configured = False


def _parse_otlp_headers(value: str | None) -> Mapping[str, str]:
    if value is None or not value.strip():
        return {}
    headers: dict[str, str] = {}
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        name, separator, header_value = item.partition("=")
        if not separator or not name.strip() or not header_value.strip():
            raise ValueError("OTEL_EXPORTER_OTLP_HEADERS_INVALID")
        headers[name.strip()] = header_value.strip()
    return headers


class SafeOtelHandler(logging.Handler):
    def __init__(
        self,
        *,
        service_name: str,
        environment: str,
    ) -> None:
        super().__init__(level=logging.INFO)
        self._service_name = service_name
        self._environment = environment

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload = build_safe_log_payload(
                record,
                service_name=self._service_name,
                environment=self._environment,
            )
            message = str(payload.pop("message"))
            payload.pop("timestamp", None)
            payload.pop("level", None)
            payload.pop("logger", None)
            attributes = {
                key: (
                    value
                    if isinstance(value, (str, bool, int, float))
                    else str(value)
                )
                for key, value in payload.items()
            }
            get_logger(record.name).emit(
                body=message,
                severity_text=record.levelname,
                attributes=attributes,
                context=get_current(),
            )
        except Exception:
            self.handleError(record)


def configure_telemetry(
    application: FastAPI,
    *,
    settings: Settings,
    engine: AsyncEngine,
) -> None:
    global _configured
    if _configured or not settings.otel_enabled:
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.application_version,
            "deployment.environment.name": settings.environment,
            "hamoon.git_commit": settings.git_commit,
            "hamoon.image_id": settings.image_id,
            "hamoon.deployment_id": settings.deployment_id,
        }
    )
    headers = _parse_otlp_headers(
        settings.otel_exporter_otlp_headers.get_secret_value()
        if settings.otel_exporter_otlp_headers is not None
        else None
    )

    provider = TracerProvider(resource=resource)
    if settings.otel_exporter_otlp_endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=settings.otel_exporter_otlp_endpoint,
                    headers=headers,
                )
            )
        )
    trace.set_tracer_provider(provider)

    if settings.otel_exporter_otlp_logs_endpoint:
        log_provider = LoggerProvider(resource=resource)
        log_provider.add_log_record_processor(
            BatchLogRecordProcessor(
                OTLPLogExporter(
                    endpoint=settings.otel_exporter_otlp_logs_endpoint,
                    headers=headers,
                )
            )
        )
        set_logger_provider(log_provider)
        hamoon_logger = logging.getLogger("hamoon")
        if not any(
            isinstance(handler, SafeOtelHandler)
            for handler in hamoon_logger.handlers
        ):
            hamoon_logger.addHandler(
                SafeOtelHandler(
                    service_name=settings.otel_service_name,
                    environment=settings.environment,
                )
            )

    FastAPIInstrumentor.instrument_app(application)
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    HTTPXClientInstrumentor().instrument()
    _configured = True
