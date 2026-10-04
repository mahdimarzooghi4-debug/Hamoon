from __future__ import annotations

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import (  # pyright: ignore[reportMissingTypeStubs]
    SQLAlchemyInstrumentor,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy.ext.asyncio import AsyncEngine

from hamoon.app.config.settings import Settings

_configured = False


def configure_telemetry(
    application: FastAPI,
    *,
    settings: Settings,
    engine: AsyncEngine,
) -> None:
    global _configured
    if _configured or not settings.otel_enabled:
        return

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.otel_service_name,
                "service.version": settings.application_version,
                "deployment.environment.name": settings.environment,
                "hamoon.git_commit": settings.git_commit,
                "hamoon.image_id": settings.image_id,
                "hamoon.deployment_id": settings.deployment_id,
            }
        )
    )
    if settings.otel_exporter_otlp_endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=settings.otel_exporter_otlp_endpoint,
                )
            )
        )
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(application)
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    HTTPXClientInstrumentor().instrument()
    _configured = True
