from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from hamoon.app.config.settings import Settings, get_settings
from hamoon.infrastructure.db.session import check_database

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["alive", "ready", "degraded"]
    service: str
    environment: str


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
