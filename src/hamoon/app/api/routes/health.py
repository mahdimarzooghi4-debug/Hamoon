from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from hamoon.app.config.settings import Settings, get_settings
from hamoon.infrastructure.db.session import (
    check_database,
    database_migration_versions,
)

router = APIRouter(tags=["health"])


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
