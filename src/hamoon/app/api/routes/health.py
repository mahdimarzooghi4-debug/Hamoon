import logging
import secrets
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from opentelemetry import trace
from pydantic import BaseModel

from hamoon.app.config.settings import Settings, get_settings
from hamoon.infrastructure.db.session import (
    check_database,
    database_migration_versions,
)

router = APIRouter(tags=["health"])

logger = logging.getLogger("hamoon.observability")
telemetry_tracer = trace.get_tracer("hamoon.observability.probe")


class HealthResponse(BaseModel):
    status: Literal["alive", "ready", "degraded"]
    service: str
    environment: str


class ReleaseIdentityResponse(BaseModel):
    status: Literal["ready", "degraded"]
    service: str
    environment: str
    application_version: str
    git_commit: str
    image_id: str
    deployment_id: str
    database_migration_versions: list[str]


class TelemetryProbeResponse(BaseModel):
    status: Literal["emitted"]
    probe_id: str
    trace_id: str
    span_id: str
    service: str
    environment: str
    git_commit: str
    deployment_id: str


@router.get("/health/live", response_model=HealthResponse)
async def liveness(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="alive",
        service=settings.app_name,
        environment=settings.environment,
    )


@router.get("/health/ready", response_model=HealthResponse)
async def readiness(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    database_ready = await check_database()

    if not database_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(
            status="degraded",
            service=settings.app_name,
            environment=settings.environment,
        )

    return HealthResponse(
        status="ready",
        service=settings.app_name,
        environment=settings.environment,
    )


@router.get("/health/release", response_model=ReleaseIdentityResponse)
async def release_identity(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> ReleaseIdentityResponse:
    try:
        migration_versions = list(await database_migration_versions())
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReleaseIdentityResponse(
            status="degraded",
            service=settings.app_name,
            environment=settings.environment,
            application_version=settings.application_version,
            git_commit=settings.git_commit,
            image_id=settings.image_id,
            deployment_id=settings.deployment_id,
            database_migration_versions=[],
        )

    if not migration_versions:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        release_status: Literal["ready", "degraded"] = "degraded"
    else:
        release_status = "ready"

    return ReleaseIdentityResponse(
        status=release_status,
        service=settings.app_name,
        environment=settings.environment,
        application_version=settings.application_version,
        git_commit=settings.git_commit,
        image_id=settings.image_id,
        deployment_id=settings.deployment_id,
        database_migration_versions=migration_versions,
    )


@router.post(
    "/health/telemetry-probe",
    response_model=TelemetryProbeResponse,
    include_in_schema=False,
)
async def telemetry_probe(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> TelemetryProbeResponse:
    expected_token = (
        settings.metrics_access_token.get_secret_value().strip()
        if settings.metrics_access_token is not None
        else ""
    )
    provided_token = request.headers.get("X-Hamoon-Metrics-Token", "")
    if (
        not expected_token
        or not secrets.compare_digest(provided_token, expected_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"Cache-Control": "no-store"},
        )

    probe_id = f"hamoon-otel-{uuid4().hex}"
    with telemetry_tracer.start_as_current_span(
        "hamoon.observability.probe"
    ) as span:
        span.set_attribute("hamoon.probe_id", probe_id)
        span.set_attribute("hamoon.git_commit", settings.git_commit)
        span.set_attribute("hamoon.deployment_id", settings.deployment_id)
        context = span.get_span_context()
        trace_id = format(context.trace_id, "032x")
        span_id = format(context.span_id, "016x")
        logger.info(
            "Observability verification probe emitted",
            extra={
                "operation": "observability_probe",
                "event_id": probe_id,
            },
        )

    return TelemetryProbeResponse(
        status="emitted",
        probe_id=probe_id,
        trace_id=trace_id,
        span_id=span_id,
        service=settings.otel_service_name,
        environment=settings.environment,
        git_commit=settings.git_commit,
        deployment_id=settings.deployment_id,
    )
