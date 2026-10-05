from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.identity.domain.entities import ActorType
from hamoon.domains.intervention.domain.entities import InterventionType
from hamoon.domains.provider.domain.entities import (
    Provider,
    ProviderService,
    ProviderStatus,
)
from hamoon.domains.referral.api import routes as referral_routes
from hamoon.domains.referral.domain.entities import (
    Referral,
    ReferralDataItem,
    ReferralStatus,
)

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD_ID = UUID("22222222-2222-2222-2222-222222222222")
INTERVENTION_ID = UUID("33333333-3333-3333-3333-333333333333")
REFERRAL_ID = UUID("44444444-4444-4444-4444-444444444444")
MATCH_ID = UUID("55555555-5555-5555-5555-555555555555")
SELECTION_ID = UUID("66666666-6666-6666-6666-666666666666")
PROVIDER_ID = UUID("77777777-7777-7777-7777-777777777777")
SERVICE_ID = UUID("88888888-8888-8888-8888-888888888888")


def _referral() -> Referral:
    return Referral(
        id=REFERRAL_ID,
        household_id=HOUSEHOLD_ID,
        intervention_id=INTERVENTION_ID,
        provider_match_id=MATCH_ID,
        provider_selection_id=SELECTION_ID,
        provider_id=PROVIDER_ID,
        provider_service_id=SERVICE_ID,
        status=ReferralStatus.SENT,
        priority="NORMAL",
        version=2,
        response_due_at=None,
        sent_at=datetime.now(UTC),
        accepted_at=None,
        completed_at=None,
        cancelled_at=None,
        external_referral_id="EXT-REF-1",
        subject_reference="SUBJECT-1",
        created_by=ACTOR_ID,
        created_at=datetime.now(UTC),
        data_items=(
            ReferralDataItem(
                id=UUID("99999999-9999-9999-9999-999999999999"),
                referral_id=REFERRAL_ID,
                data_category="geo.coverage_code",
                source_fact_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                snapshot_value="TEHRAN-1",
                purpose="SERVICE_ELIGIBILITY",
                authorization_basis="CASEWORKER_REFERRAL_SEND",
                shared_at=datetime.now(UTC),
            ),
        ),
    )


class InterventionRepo:
    async def get(self, intervention_id: UUID) -> object | None:
        if intervention_id != INTERVENTION_ID:
            return None
        return SimpleNamespace(household_id=HOUSEHOLD_ID)


class ReferralRepo:
    def __init__(self, item: Referral | None) -> None:
        self.item = item

    async def get_latest_for_intervention(
        self,
        intervention_id: UUID,
    ) -> Referral | None:
        if intervention_id != INTERVENTION_ID:
            return None
        return self.item


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
async def test_caseworker_can_read_latest_referral_with_display_fields(
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
        referral_routes,
        "SqlAlchemyInterventionRepository",
        lambda _session: InterventionRepo(),
    )
    monkeypatch.setattr(
        referral_routes,
        "SqlAlchemyReferralRepository",
        lambda _session: ReferralRepo(_referral()),
    )
    monkeypatch.setattr(
        referral_routes,
        "SqlAlchemyProviderRegistryRepository",
        lambda _session: Registry(),
    )
    monkeypatch.setattr(referral_routes, "require_household_assignment", require_scope)

    response = await referral_routes.get_latest_referral(
        INTERVENTION_ID,
        _context(),
        cast(AsyncSession, object()),
    )

    assert scoped == [HOUSEHOLD_ID]
    assert response.data.id == REFERRAL_ID
    assert response.data.provider_name == "مرکز کاریابی منطقه ۱۲"
    assert response.data.service_title == "پیوند با بازار کار"
    assert response.data.status is ReferralStatus.SENT
    assert response.data.version == 2


@pytest.mark.asyncio
async def test_latest_referral_returns_not_found_when_missing(
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
        referral_routes,
        "SqlAlchemyInterventionRepository",
        lambda _session: InterventionRepo(),
    )
    monkeypatch.setattr(
        referral_routes,
        "SqlAlchemyReferralRepository",
        lambda _session: ReferralRepo(None),
    )
    monkeypatch.setattr(referral_routes, "require_household_assignment", require_scope)

    with pytest.raises(HTTPException) as exc_info:
        await referral_routes.get_latest_referral(
            INTERVENTION_ID,
            _context(),
            cast(AsyncSession, object()),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == {"code": "REFERRAL_NOT_FOUND"}


def test_provider_callback_request_rejects_unsupported_schema_version() -> None:
    from hamoon.domains.referral.api.schemas import ProviderStatusCallbackRequest

    with pytest.raises(ValidationError):
        ProviderStatusCallbackRequest(
            external_event_id="evt-schema-2",
            status=ReferralStatus.ACCEPTED,
            occurred_at=datetime.now(UTC),
            schema_version="2",
        )
