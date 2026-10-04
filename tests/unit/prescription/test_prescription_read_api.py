from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.identity.domain.entities import ActorType
from hamoon.domains.intelligence.domain.decisions import (
    AIDecision,
    AIDecisionStatus,
    AIDecisionType,
    HumanDecision,
    HumanDecisionAction,
    HumanDecisionContext,
)
from hamoon.domains.intervention.domain.entities import InterventionType
from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.prescription.api import routes as prescription_routes
from hamoon.domains.prescription.domain.entities import (
    Prescription,
    PrescriptionItem,
    PrescriptionItemStatus,
    PrescriptionStatus,
)

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD_ID = UUID("22222222-2222-2222-2222-222222222222")
PRESCRIPTION_ID = UUID("33333333-3333-3333-3333-333333333333")
DIAGNOSIS_ID = UUID("44444444-4444-4444-4444-444444444444")
AI_DECISION_ID = UUID("55555555-5555-5555-5555-555555555555")
PGOR_ID = UUID("66666666-6666-6666-6666-666666666666")
ITEM_ID = UUID("77777777-7777-7777-7777-777777777777")
HUMAN_DECISION_ID = UUID("88888888-8888-8888-8888-888888888888")
ASSESSMENT_ID = UUID("99999999-9999-9999-9999-999999999999")
FEATURE_PACKAGE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ROUTING_POLICY_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TRACE_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _context() -> AuthorizationContext:
    return AuthorizationContext(
        actor_id=ACTOR_ID,
        actor_type=ActorType.HUMAN,
        subject="caseworker",
        issuer="https://identity.local",
        roles=frozenset({Role.CASEWORKER}),
        scopes=frozenset(),
    )


def _prescription() -> Prescription:
    now = datetime(2026, 10, 4, 10, 30, tzinfo=UTC)
    return Prescription(
        id=PRESCRIPTION_ID,
        household_id=HOUSEHOLD_ID,
        diagnosis_id=DIAGNOSIS_ID,
        ai_decision_id=AI_DECISION_ID,
        pgor_snapshot_id=PGOR_ID,
        status=PrescriptionStatus.MODIFIED,
        version=2,
        accepted_payload={
            "schema_version": "prescription-v1",
            "summary": "نسخه نهایی",
            "intensity_score": "0.46",
            "items": [],
            "review_flags": ["HUMAN_REVIEW_REQUIRED"],
        },
        created_at=now,
        created_by=ACTOR_ID,
        latest_human_decision_id=HUMAN_DECISION_ID,
        accepted_at=now,
        accepted_by=ACTOR_ID,
    )


def _ai_decision() -> AIDecision:
    now = datetime(2026, 10, 4, 10, 25, tzinfo=UTC)
    return AIDecision(
        id=AI_DECISION_ID,
        household_id=HOUSEHOLD_ID,
        assessment_id=ASSESSMENT_ID,
        feature_package_id=FEATURE_PACKAGE_ID,
        pgor_snapshot_id=PGOR_ID,
        decision_type=AIDecisionType.PRESCRIPTION,
        status=AIDecisionStatus.GENERATED,
        provider_code="FAKE",
        model_id="fake-prescription-v1",
        model_alias="hamoon.prescription.v1",
        routing_policy_id=ROUTING_POLICY_ID,
        routing_policy_version="local-prescription-test-v1",
        prompt_policy_version="prescription-prompt-v1",
        output_schema_version="prescription-v1",
        structured_output={
            "schema_version": "prescription-v1",
            "summary": "نسخه پیشنهادی",
            "intensity_score": "0.46",
            "items": [],
            "review_flags": ["HUMAN_REVIEW_REQUIRED"],
        },
        trace_id=TRACE_ID,
        generated_at=now,
    )


def _human_decision() -> HumanDecision:
    now = datetime(2026, 10, 4, 10, 30, tzinfo=UTC)
    payload = _prescription().accepted_payload
    return HumanDecision(
        id=HUMAN_DECISION_ID,
        household_id=HOUSEHOLD_ID,
        ai_decision_id=AI_DECISION_ID,
        actor_id=ACTOR_ID,
        action=HumanDecisionAction.MODIFY,
        reason_code="PROFESSIONAL_JUDGMENT",
        reason_text="یک مداخله تکمیلی اضافه شد.",
        accepted_payload=payload,
        modified_payload=payload,
        decided_at=now,
        decision_context=HumanDecisionContext.PRESCRIPTION,
        prescription_id=PRESCRIPTION_ID,
    )


def _item() -> PrescriptionItem:
    return PrescriptionItem(
        id=ITEM_ID,
        prescription_id=PRESCRIPTION_ID,
        source_code="EMPLOYMENT_NETWORK",
        intervention_type=InterventionType.NETWORKING,
        target_pgor_variable=PGORVariableCode.O,
        priority=1,
        current_value=None,
        target_value=None,
        success_criteria=("اتصال به شبکه حرفه‌ای",),
        review_after_days=30,
        review_rationale="بررسی اثر مداخله پس از یک ماه",
        rationale="برای رفع محدودیت فرصت",
        title="توسعه شبکه حرفه‌ای",
        status=PrescriptionItemStatus.ACCEPTED,
        machine_proposed=False,
    )


class Prescriptions:
    async def list_for_household(
        self,
        household_id: UUID,
        *,
        limit: int,
    ) -> list[Prescription]:
        assert household_id == HOUSEHOLD_ID
        assert limit == 50
        return [_prescription()]

    async def list_items_for_prescriptions(
        self,
        prescription_ids: list[UUID],
    ) -> dict[UUID, list[PrescriptionItem]]:
        assert prescription_ids == [PRESCRIPTION_ID]
        return {PRESCRIPTION_ID: [_item()]}


class AIDecisions:
    async def list_by_ids(
        self,
        decision_ids: list[UUID],
    ) -> dict[UUID, AIDecision]:
        assert decision_ids == [AI_DECISION_ID]
        return {AI_DECISION_ID: _ai_decision()}


class HumanDecisions:
    async def list_for_prescriptions(
        self,
        prescription_ids: list[UUID],
    ) -> dict[UUID, list[HumanDecision]]:
        assert prescription_ids == [PRESCRIPTION_ID]
        return {PRESCRIPTION_ID: [_human_decision()]}


@pytest.mark.asyncio
async def test_list_household_prescriptions_returns_history_and_items(
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
        prescription_routes,
        "require_household_assignment",
        require_scope,
    )
    monkeypatch.setattr(
        prescription_routes,
        "SqlAlchemyPrescriptionRepository",
        lambda _session: Prescriptions(),
    )
    monkeypatch.setattr(
        prescription_routes,
        "SqlAlchemyAIDecisionRepository",
        lambda _session: AIDecisions(),
    )
    monkeypatch.setattr(
        prescription_routes,
        "SqlAlchemyHumanDecisionRepository",
        lambda _session: HumanDecisions(),
    )

    response = await prescription_routes.list_household_prescriptions(
        HOUSEHOLD_ID,
        _context(),
        cast(AsyncSession, object()),
        limit=50,
    )

    assert scoped == [HOUSEHOLD_ID]
    assert len(response.data) == 1
    item = response.data[0]
    assert item.id == PRESCRIPTION_ID
    assert item.machine_proposal["summary"] == "نسخه پیشنهادی"
    assert item.accepted_payload is not None
    assert item.accepted_payload["summary"] == "نسخه نهایی"
    assert item.model_alias == "hamoon.prescription.v1"
    assert len(item.human_decisions) == 1
    assert item.human_decisions[0].action is HumanDecisionAction.MODIFY
    assert len(item.accepted_items) == 1
    assert item.accepted_items[0].id == ITEM_ID
    assert item.accepted_items[0].machine_proposed is False


@pytest.mark.asyncio
async def test_list_household_prescriptions_rejects_invalid_limit(
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
        prescription_routes,
        "require_household_assignment",
        require_scope,
    )

    with pytest.raises(Exception) as exc_info:
        await prescription_routes.list_household_prescriptions(
            HOUSEHOLD_ID,
            _context(),
            cast(AsyncSession, object()),
            limit=0,
        )

    assert getattr(exc_info.value, "status_code", None) == 422
