from fastapi import APIRouter

from hamoon.app.api.routes.health import router as health_router
from hamoon.domains.assessment.api.routes import router as assessment_router
from hamoon.domains.family_data.api.routes import router as family_data_router
from hamoon.domains.household.api.routes import router as household_router
from hamoon.domains.intelligence.api.routes import router as intelligence_router
from hamoon.domains.pgor.api.routes import router as pgor_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(household_router)
api_router.include_router(family_data_router)
api_router.include_router(assessment_router)
api_router.include_router(pgor_router)
api_router.include_router(intelligence_router)
