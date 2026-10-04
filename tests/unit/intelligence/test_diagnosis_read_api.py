from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.identity.domain.entities import ActorType
from hamoon.domains.intelligence.api import routes as intelligence_routes
from hamoon.domains.intelligence.domain.decisions import (
    AIDecision,
    AIDecisionStatus,
    AIDecisionType,
    Diagnosis,
    DiagnosisStatus,
    HumanDecision,
    HumanDecisionAction,
    HumanDecisionContext,
)

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD_ID = UUID("22222222-2222-2222-2222-222222222222")
DIAGNOSIS_ID = UUID("33333333-3333-3333-3333-333333333333")
AI_DECISION_ID = UUID("44444444-4444-4444-4444-444444444444")
HUMAN_DECISION_ID = UUID("55555555-5555-5555-5555-555555555555")
ASSESSMENT_ID = UUID("66666666-6666-6666-6666-666666666666")
FEATURE_PACKAGE_ID = UUID("77777777-7777-7777-7777-777777777777")
PGOR_SNAPSHOT_ID = UUID("88888888-8888-8888-8888-888888888888")
ROUTING_POLICY_ID = UUID("99999999-9999-9999-9999-999999999999")
TRACE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _context() -> AuthorizationContext:
    return AuthorizationContext(
        actor_id=ACTOR_ID,
        actor_type=ActorType.HUMAN,
        subject="caseworker",
        issuer="https://identity.local",
        roles=frozenset({Role.CASEWORKER}),
        scopes=frozenset(),
    )


def _diagnosis() -> Diagnosis:
    now = datetime(2026, 10, 4, 10, 0, tzinfo=UTC)
    return Diagnosis(
        id=DIAGNOSIS_ID,
        household_id=HOUSEHOLD_ID,
        ai_decision_id=AI_DECISION_ID,
        status=DiagnosisStatus.MODIFIED,
        version=2,
        accepted_payload={
            "schema_version": "diagnosis-v1",
            "summary": "تشخیص نهایی",
            "items": [],
            "review_flags": [],
        },
        created_at=now,
        latest_human_decision_id=HUMAN_DECISION_ID,
        reviewed_at=now,
        reviewed_by=ACTOR_ID,
    )


def _ai_decision() -> AIDecision:
    now = datetime(2026, 10, 4, 9, 55, tzinfo=UTC)
    return AIDecision(
        id=AI_DECISION_ID,
        household_id=HOUSEHOLD_ID,
        assessment_id=ASSESSMENT_ID,
        feature_package_id=FEATURE_PACKAGE_ID,
        pgor_snapshot_id=PGOR_SNAPSHOT_ID,
        decision_type=AIDecisionType.DIAGNOSIS,
        status=AIDecisionStatus.GENERATED,
        provider_code="FAKE",
        model_id="fake-diagnosis-v1",
        model_alias="hamoon.diagnosis.v1",
        routing_policy_id=ROUTING_POLICY_ID,
        routing_policy_version="local-test-v1",
        prompt_policy_version="diagnosis-prompt-v1",
        output_schema_version="diagnosis-v1",
        structured_output={
            "schema_version": "diagnosis-v1",
            "summary": "پیشنهاد هامون",
            "items": [],
            "review_flags": [],
        },
        trace_id=TRACE_ID,
        generated_at=now,
    )


def _human_decision() -> HumanDecision:
    now = datetime(2026, 10, 4, 10, 0, tzinfo=UTC)
    return HumanDecision(
        id=HUMAN_DECISION_ID,
        household_id=HOUSEHOLD_ID,
        ai_decision_id=AI_DECISION_ID,
        actor_id=ACTOR_ID,
        action=HumanDecisionAction.MODIFY,
        reason_code="PROFESSIONAL_JUDGMENT",
        reason_text="نیاز به اصلاح حرفه‌ای داشت.",
        accepted_payload={
            "schema_version": "diagnosis-v1",
            "summary": "تشخیص نهایی",
            "items": [],
            "review_flags": [],
        },
        modified_payload={
            "schema_version": "diagnosis-v1",
            "summary": "تشخیص نهایی",
            "items": [],
            "review_flags": [],
        },
        decided_at=now,
        decision_context=HumanDecisionContext.DIAGNOSIS,
        diagnosis_id=DIAGNOSIS_ID,
    )


class Diagnoses:
    async def list_for_household(
        self,
        household_id: UUID,
        *,
        limit: int,
    ) -> list[Diagnosis]:
        assert household_id == HOUSEHOLD_ID
        assert limit == 50
        return [_diagnosis()]


class AIDecisions:
    async def list_by_ids(
        self,
        decision_ids: list[UUID],
    ) -> dict[UUID, AIDecision]:
        assert decision_ids == [AI_DECISION_ID]
        return {AI_DECISION_ID: _ai_decision()}


class HumanDecisions:
    async def list_for_diagnoses(
        self,
        diagnosis_ids: list[UUID],
    ) -> dict[UUID, list[HumanDecision]]:
        assert diagnosis_ids == [DIAGNOSIS_ID]
        return {DIAGNOSIS_ID: [_human_decision()]}


@pytest.mark.asyncio
async def test_list_household_diagnoses_returns_machine_and_human_history(
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
        intelligence_routes,
        "require_household_assignment",
        require_scope,
    )
    monkeypatch.setattr(
        intelligence_routes,
        "SqlAlchemyDiagnosisRepository",
        lambda _session: Diagnoses(),
    )
    monkeypatch.setattr(
        intelligence_routes,
        "SqlAlchemyAIDecisionRepository",
        lambda _session: AIDecisions(),
    )
    monkeypatch.setattr(
        intelligence_routes,
        "SqlAlchemyHumanDecisionRepository",
        lambda _session: HumanDecisions(),
    )

    response = await intelligence_routes.list_household_diagnoses(
        HOUSEHOLD_ID,
        _context(),
        cast(AsyncSession, object()),
        limit=50,
    )

    assert scoped == [HOUSEHOLD_ID]
    assert len(response.data) == 1
    item = response.data[0]
    assert item.id == DIAGNOSIS_ID
    assert item.machine_proposal["summary"] == "پیشنهاد هامون"
    assert item.accepted_payload is not None
    assert item.accepted_payload["summary"] == "تشخیص نهایی"
    assert item.model_alias == "hamoon.diagnosis.v1"
    assert len(item.human_decisions) == 1
    assert item.human_decisions[0].action is HumanDecisionAction.MODIFY
    assert item.human_decisions[0].reason_code == "PROFESSIONAL_JUDGMENT"


@pytest.mark.asyncio
async def test_list_household_diagnoses_rejects_invalid_limit(
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
        intelligence_routes,
        "require_household_assignment",
        require_scope,
    )

    with pytest.raises(Exception) as exc_info:
        await intelligence_routes.list_household_diagnoses(
            HOUSEHOLD_ID,
            _context(),
            cast(AsyncSession, object()),
            limit=0,
        )

    assert getattr(exc_info.value, "status_code", None) == 422
