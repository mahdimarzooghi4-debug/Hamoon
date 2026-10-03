from fastapi import APIRouter

from hamoon.app.api.routes.health import router as health_router
from hamoon.domains.household.api.routes import router as household_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(household_router)
