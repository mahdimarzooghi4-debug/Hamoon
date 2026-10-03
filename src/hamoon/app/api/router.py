from fastapi import APIRouter

from hamoon.app.api.routes.health import router as health_router
from hamoon.domains.assessment.api.routes import router as assessment_router
from hamoon.domains.family_data.api.routes import router as family_data_router
from hamoon.domains.household.api.routes import router as household_router
from hamoon.domains.intelligence.api.routes import router as intelligence_router
from hamoon.domains.intervention.api.routes import router as intervention_router
from hamoon.domains.learning.api.routes import router as learning_router
from hamoon.domains.outcome.api.routes import router as outcome_router
from hamoon.domains.pgor.api.routes import router as pgor_router
from hamoon.domains.prescription.api.routes import router as prescription_router
from hamoon.domains.provider.api.routes import router as provider_router
from hamoon.domains.provider_result.api.routes import router as provider_result_router
from hamoon.domains.referral.api.routes import router as referral_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(household_router)
api_router.include_router(family_data_router)
api_router.include_router(assessment_router)
api_router.include_router(pgor_router)
api_router.include_router(intelligence_router)
api_router.include_router(intervention_router)
api_router.include_router(prescription_router)
api_router.include_router(provider_router)
api_router.include_router(referral_router)
api_router.include_router(provider_result_router)
api_router.include_router(outcome_router)
api_router.include_router(learning_router)
