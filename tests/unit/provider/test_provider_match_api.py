from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.identity.domain.entities import ActorType
from hamoon.domains.intervention.domain.entities import InterventionType
from hamoon.domains.provider.api import routes as provider_routes
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


def _match() -> ProviderMatch:
    return ProviderMatch(
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


class InterventionRepo:
    async def get(self, intervention_id: UUID) -> object | None:
        if intervention_id != INTERVENTION_ID:
            return None
        return type("InterventionRef", (), {"household_id": HOUSEHOLD_ID})()


class MatchRepo:
    def __init__(self, item: ProviderMatch | None) -> None:
        self.item = item

    async def get_latest_for_intervention(
        self,
        intervention_id: UUID,
    ) -> ProviderMatch | None:
        if intervention_id != INTERVENTION_ID:
            return None
        return self.item


def _context() -> AuthorizationContext:
    return AuthorizationContext(
        actor_id=ACTOR_ID,
        actor_type=ActorType.HUMAN,
        subject="caseworker-subject",
        issuer="https://identity.local",
        roles=frozenset({Role.CASEWORKER}),
        scopes=frozenset(),
    )


@pytest.mark.asyncio
async def test_caseworker_can_read_latest_provider_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scoped: list[UUID] = []

    async def require_scope(
        *,
        session: AsyncSession,
        context: AuthorizationContext,
        household_id: UUID,
    ) -> None:
        del session, context
        scoped.append(household_id)

    monkeypatch.setattr(
        provider_routes,
        "SqlAlchemyInterventionRepository",
        lambda _session: InterventionRepo(),
    )
    monkeypatch.setattr(
        provider_routes,
        "SqlAlchemyProviderMatchRepository",
        lambda _session: MatchRepo(_match()),
    )
    monkeypatch.setattr(
        provider_routes,
        "SqlAlchemyProviderRegistryRepository",
        lambda _session: Registry(),
    )
    monkeypatch.setattr(provider_routes, "require_household_assignment", require_scope)

    response = await provider_routes.get_latest_provider_match(
        INTERVENTION_ID,
        _context(),
        cast(AsyncSession, object()),
    )

    assert scoped == [HOUSEHOLD_ID]
    assert response.data.provider_match_id == MATCH_ID
    assert response.data.household_context_version == 3
    assert response.data.candidates[0].provider_name == "مرکز کاریابی منطقه ۱۲"
    assert response.data.candidates[0].service_title == "پیوند با بازار کار"


@pytest.mark.asyncio
async def test_latest_provider_match_returns_not_found_when_no_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def require_scope(
        *,
        session: AsyncSession,
        context: AuthorizationContext,
        household_id: UUID,
    ) -> None:
        del session, context, household_id

    monkeypatch.setattr(
        provider_routes,
        "SqlAlchemyInterventionRepository",
        lambda _session: InterventionRepo(),
    )
    monkeypatch.setattr(
        provider_routes,
        "SqlAlchemyProviderMatchRepository",
        lambda _session: MatchRepo(None),
    )
    monkeypatch.setattr(provider_routes, "require_household_assignment", require_scope)

    with pytest.raises(HTTPException) as exc_info:
        await provider_routes.get_latest_provider_match(
            INTERVENTION_ID,
            _context(),
            cast(AsyncSession, object()),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == {"code": "PROVIDER_MATCH_NOT_FOUND"}
