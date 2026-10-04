from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest

from hamoon.domains.intervention.domain.entities import InterventionType
from hamoon.domains.provider.api.routes import _provider_match_data
from hamoon.domains.provider.domain.entities import (
    CapacityStatus,
    MatchEligibility,
    Provider,
    ProviderMatch,
    ProviderMatchCandidate,
    ProviderService,
    ProviderStatus,
)
from hamoon.domains.provider.infrastructure.repositories import (
    SqlAlchemyProviderRegistryRepository,
)

MATCH_ID = UUID("11111111-1111-1111-1111-111111111111")
INTERVENTION_ID = UUID("22222222-2222-2222-2222-222222222222")
HOUSEHOLD_ID = UUID("33333333-3333-3333-3333-333333333333")
PROVIDER_ID = UUID("44444444-4444-4444-4444-444444444444")
SERVICE_ID = UUID("55555555-5555-5555-5555-555555555555")
ACTOR_ID = UUID("66666666-6666-6666-6666-666666666666")


class Registry:
    async def get_provider(self, provider_id: UUID) -> Provider | None:
        if provider_id != PROVIDER_ID:
            return None
        return Provider(
            id=PROVIDER_ID,
            code="employment-center-12",
            name="مرکز کاریابی منطقه ۱۲",
            status=ProviderStatus.ACTIVE,
            organization_type="EMPLOYMENT_CENTER",
            integration_mode="API",
            created_at=datetime.now(UTC),
        )

    async def get_service(self, service_id: UUID) -> ProviderService | None:
        if service_id != SERVICE_ID:
            return None
        return ProviderService(
            id=SERVICE_ID,
            provider_id=PROVIDER_ID,
            service_type="EMPLOYMENT_MARKET",
            title="پیوند با بازار کار",
            description="",
            supported_intervention_types=(InterventionType.MARKET_LINKAGE,),
            eligibility_policy_version="elig-v1",
            coverage_policy_version="coverage-v1",
            coverage_fact_type="geo.coverage_code",
            coverage_codes=("TEHRAN-1",),
            sla_policy_version="sla-v1",
            active=True,
        )


@pytest.mark.asyncio
async def test_provider_match_candidate_includes_caseworker_display_fields() -> None:
    match = ProviderMatch(
        id=MATCH_ID,
        household_id=HOUSEHOLD_ID,
        intervention_id=INTERVENTION_ID,
        service_type="EMPLOYMENT_MARKET",
        household_context_version=3,
        matching_policy_version="provider-match-rules-v1",
        generated_at=datetime.now(UTC),
        generated_by=ACTOR_ID,
        candidates=(
            ProviderMatchCandidate(
                id=UUID("77777777-7777-7777-7777-777777777777"),
                provider_match_id=MATCH_ID,
                provider_id=PROVIDER_ID,
                provider_service_id=SERVICE_ID,
                eligibility=MatchEligibility.ELIGIBLE,
                capacity_status=CapacityStatus.AVAILABLE,
                reasons=(),
            ),
        ),
    )

    data = await _provider_match_data(
        match=match,
        registry=cast(SqlAlchemyProviderRegistryRepository, Registry()),
    )

    assert len(data.candidates) == 1
    candidate = data.candidates[0]
    assert candidate.provider_id == PROVIDER_ID
    assert candidate.provider_name == "مرکز کاریابی منطقه ۱۲"
    assert candidate.provider_service_id == SERVICE_ID
    assert candidate.service_title == "پیوند با بازار کار"
    assert candidate.eligibility is MatchEligibility.ELIGIBLE
    assert candidate.capacity_status is CapacityStatus.AVAILABLE
