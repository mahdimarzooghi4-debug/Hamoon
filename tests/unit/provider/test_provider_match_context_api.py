from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.family_data.domain.entities import CurrentAcceptedFact
from hamoon.domains.identity.domain.entities import ActorType
from hamoon.domains.intervention.domain.entities import InterventionType
from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.provider.api import routes as provider_routes
from hamoon.domains.provider.api.schemas import MatchProvidersRequest
from hamoon.domains.provider.domain.entities import ProviderService

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD_ID = UUID("22222222-2222-2222-2222-222222222222")
INTERVENTION_ID = UUID("33333333-3333-3333-3333-333333333333")
FACT_ID = UUID("44444444-4444-4444-4444-444444444444")
SOURCE_ID = UUID("55555555-5555-5555-5555-555555555555")
PROVIDER_ID = UUID("66666666-6666-6666-6666-666666666666")
SERVICE_ID = UUID("77777777-7777-7777-7777-777777777777")
OTHER_SERVICE_ID = UUID("88888888-8888-8888-8888-888888888888")


def _context() -> AuthorizationContext:
    return AuthorizationContext(
        actor_id=ACTOR_ID,
        actor_type=ActorType.HUMAN,
        subject="caseworker",
        issuer="https://identity.local",
        roles=frozenset({Role.CASEWORKER}),
        scopes=frozenset(),
    )


class Interventions:
    async def get(self, intervention_id: UUID) -> object | None:
        if intervention_id != INTERVENTION_ID:
            return None
        return SimpleNamespace(
            id=INTERVENTION_ID,
            household_id=HOUSEHOLD_ID,
            intervention_type=InterventionType.MARKET_LINKAGE,
            target_pgor_variable=PGORVariableCode.O,
        )


class Accepted:
    async def list_for_household(
        self,
        household_id: UUID,
    ) -> list[CurrentAcceptedFact]:
        assert household_id == HOUSEHOLD_ID
        return [
            CurrentAcceptedFact(
                household_id=HOUSEHOLD_ID,
                fact_type="geo.coverage_code",
                fact_id=FACT_ID,
                accepted_value="TEHRAN-1",
                source_id=SOURCE_ID,
                effective_from=datetime(2026, 9, 1, tzinfo=UTC),
                projection_version=2,
                projected_at=datetime(2026, 9, 2, tzinfo=UTC),
                changed_by=ACTOR_ID,
            )
        ]

    async def context_version(self, household_id: UUID) -> int:
        assert household_id == HOUSEHOLD_ID
        return 3


class Registry:
    async def list_active_services(self) -> list[ProviderService]:
        return [
            ProviderService(
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
            ),
            ProviderService(
                id=OTHER_SERVICE_ID,
                provider_id=PROVIDER_ID,
                service_type="SKILLS",
                title="آموزش مهارت",
                description="",
                supported_intervention_types=(InterventionType.SKILLS_TRAINING,),
                eligibility_policy_version=None,
                coverage_policy_version=None,
                coverage_fact_type=None,
                coverage_codes=(),
                sla_policy_version=None,
                active=True,
            ),
        ]


async def _scope(
    *,
    session: AsyncSession,
    context: AuthorizationContext,
    household_id: UUID,
) -> None:
    del session, context
    assert household_id == HOUSEHOLD_ID


@pytest.mark.asyncio
async def test_provider_match_context_exposes_compatible_services_and_fact_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider_routes,
        "SqlAlchemyInterventionRepository",
        lambda _session: Interventions(),
    )
    monkeypatch.setattr(
        provider_routes,
        "SqlAlchemyAcceptedStateRepository",
        lambda _session: Accepted(),
    )
    monkeypatch.setattr(
        provider_routes,
        "SqlAlchemyProviderRegistryRepository",
        lambda _session: Registry(),
    )
    monkeypatch.setattr(provider_routes, "require_household_assignment", _scope)

    response = await provider_routes.get_provider_match_context(
        INTERVENTION_ID,
        _context(),
        cast(AsyncSession, object()),
    )

    assert response.data.household_context_version == 3
    assert response.data.intervention_type == InterventionType.MARKET_LINKAGE.value
    assert len(response.data.service_types) == 1
    assert response.data.service_types[0].service_type == "EMPLOYMENT_MARKET"
    assert response.data.service_types[0].service_titles == ["پیوند با بازار کار"]
    assert len(response.data.shareable_facts) == 1
    assert response.data.shareable_facts[0].fact_id == FACT_ID
    assert response.data.shareable_facts[0].fact_type == "geo.coverage_code"


class _Begin:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False


class FakeSession:
    def begin(self) -> _Begin:
        return _Begin()


@pytest.mark.asyncio
async def test_match_rejects_stale_household_context_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider_routes,
        "SqlAlchemyInterventionRepository",
        lambda _session: Interventions(),
    )
    monkeypatch.setattr(
        provider_routes,
        "SqlAlchemyAcceptedStateRepository",
        lambda _session: Accepted(),
    )
    monkeypatch.setattr(provider_routes, "require_household_assignment", _scope)

    with pytest.raises(HTTPException) as exc_info:
        await provider_routes.match_providers(
            INTERVENTION_ID,
            MatchProvidersRequest(
                service_type="EMPLOYMENT_MARKET",
                household_context_version=2,
            ),
            _context(),
            cast(AsyncSession, FakeSession()),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == {
        "code": "HOUSEHOLD_CONTEXT_VERSION_CONFLICT",
        "current_version": 3,
    }
