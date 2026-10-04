from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.identity.domain.entities import ActorType
from hamoon.domains.operations.domain.entities import (
    ReassessmentPlan,
    ReassessmentPlanStatus,
)
from hamoon.domains.provider_result.api import routes as provider_result_routes
from hamoon.domains.provider_result.domain.entities import ProviderResult

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD_ID = UUID("22222222-2222-2222-2222-222222222222")
REFERRAL_ID = UUID("33333333-3333-3333-3333-333333333333")
RESULT_ID = UUID("44444444-4444-4444-4444-444444444444")
PROVIDER_ID = UUID("55555555-5555-5555-5555-555555555555")
PLAN_ID = UUID("66666666-6666-6666-6666-666666666666")
INTERVENTION_ID = UUID("77777777-7777-7777-7777-777777777777")
PRESCRIPTION_ITEM_ID = UUID("88888888-8888-8888-8888-888888888888")


def _result() -> ProviderResult:
    now = datetime.now(UTC)
    return ProviderResult(
        id=RESULT_ID,
        referral_id=REFERRAL_ID,
        provider_id=PROVIDER_ID,
        result_status="COMPLETED",
        result_type="SERVICE_COMPLETION",
        result_summary="خدمت تکمیل شد.",
        result_payload={"structured": True},
        service_started_at=now - timedelta(days=7),
        service_completed_at=now,
        submitted_at=now,
        external_result_id="provider-result-1",
        provider_reference="provider-ref-1",
        request_hash="hash",
        evidence_ids=(),
    )


def _plan() -> ReassessmentPlan:
    now = datetime.now(UTC)
    return ReassessmentPlan(
        id=PLAN_ID,
        household_id=HOUSEHOLD_ID,
        intervention_id=INTERVENTION_ID,
        provider_result_id=RESULT_ID,
        prescription_item_id=PRESCRIPTION_ITEM_ID,
        assigned_actor_id=ACTOR_ID,
        review_after_days=30,
        due_at=now + timedelta(days=30),
        policy_version="reassessment-v1",
        workflow_id="reassessment-plan-1",
        status=ReassessmentPlanStatus.SCHEDULED,
        version=1,
        created_at=now,
        created_by=ACTOR_ID,
    )


class ResultRepo:
    async def get(self, result_id: UUID) -> ProviderResult | None:
        return _result() if result_id == RESULT_ID else None

    async def list_for_referral(self, referral_id: UUID) -> list[ProviderResult]:
        return [_result()] if referral_id == REFERRAL_ID else []


class ReferralRepo:
    async def get(self, referral_id: UUID) -> object | None:
        if referral_id != REFERRAL_ID:
            return None
        return SimpleNamespace(household_id=HOUSEHOLD_ID)


class PlanRepo:
    async def get_by_provider_result(
        self,
        provider_result_id: UUID,
    ) -> ReassessmentPlan | None:
        return _plan() if provider_result_id == RESULT_ID else None


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
async def test_provider_result_get_restores_reassessment_plan_after_refresh(
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
        provider_result_routes,
        "SqlAlchemyProviderResultRepository",
        lambda _session: ResultRepo(),
    )
    monkeypatch.setattr(
        provider_result_routes,
        "SqlAlchemyReferralRepository",
        lambda _session: ReferralRepo(),
    )
    monkeypatch.setattr(
        provider_result_routes,
        "SqlAlchemyReassessmentPlanRepository",
        lambda _session: PlanRepo(),
    )
    monkeypatch.setattr(
        provider_result_routes,
        "require_household_assignment",
        require_scope,
    )

    response = await provider_result_routes.get_provider_result(
        RESULT_ID,
        _context(),
        cast(AsyncSession, object()),
    )

    assert scoped == [HOUSEHOLD_ID]
    assert response.data.reassessment_plan_id == PLAN_ID
    assert response.data.reassessment_due_at == _plan().due_at
    assert response.data.workflow_id == "reassessment-plan-1"
    assert response.data.reassessment_status is ReassessmentPlanStatus.SCHEDULED


@pytest.mark.asyncio
async def test_provider_result_list_includes_persisted_reassessment_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def require_scope(
        *,
        session: AsyncSession,
        context: AuthorizationContext,
        household_id: UUID,
    ) -> None:
        del session, context
        assert household_id == HOUSEHOLD_ID

    monkeypatch.setattr(
        provider_result_routes,
        "SqlAlchemyProviderResultRepository",
        lambda _session: ResultRepo(),
    )
    monkeypatch.setattr(
        provider_result_routes,
        "SqlAlchemyReferralRepository",
        lambda _session: ReferralRepo(),
    )
    monkeypatch.setattr(
        provider_result_routes,
        "SqlAlchemyReassessmentPlanRepository",
        lambda _session: PlanRepo(),
    )
    monkeypatch.setattr(
        provider_result_routes,
        "require_household_assignment",
        require_scope,
    )

    response = await provider_result_routes.list_provider_results(
        REFERRAL_ID,
        _context(),
        cast(AsyncSession, object()),
    )

    assert len(response.data) == 1
    item = response.data[0]
    assert item.reassessment_plan_id == PLAN_ID
    assert item.reassessment_status is ReassessmentPlanStatus.SCHEDULED
