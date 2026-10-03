from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest

from hamoon.domains.intelligence.domain.decisions import HumanDecisionAction
from hamoon.domains.outcome.api import routes
from hamoon.domains.outcome.domain.entities import (
    HamoonOutcome,
    OutcomeClassification,
    OutcomeStatus,
)

ACTOR = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD = UUID("22222222-2222-2222-2222-222222222222")
OUTCOME_ID = UUID("33333333-3333-3333-3333-333333333333")
INTERVENTION = UUID("44444444-4444-4444-4444-444444444444")
PROVIDER_RESULT = UUID("55555555-5555-5555-5555-555555555555")
PRE_ASSESSMENT = UUID("66666666-6666-6666-6666-666666666666")
POST_ASSESSMENT = UUID("77777777-7777-7777-7777-777777777777")
PRE_SNAPSHOT = UUID("88888888-8888-8888-8888-888888888888")
POST_SNAPSHOT = UUID("99999999-9999-9999-9999-999999999999")
HUMAN_DECISION = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
LEARNING_SIGNAL = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


BASE_OUTCOME = HamoonOutcome(
    id=OUTCOME_ID,
    household_id=HOUSEHOLD,
    intervention_id=INTERVENTION,
    referral_id=None,
    provider_result_id=PROVIDER_RESULT,
    pre_assessment_id=PRE_ASSESSMENT,
    post_assessment_id=POST_ASSESSMENT,
    pre_pgor_snapshot_id=PRE_SNAPSHOT,
    post_pgor_snapshot_id=POST_SNAPSHOT,
    status=OutcomeStatus.UNDER_REVIEW,
    classification=None,
    observed_change_summary="Observed deterministic PGOR delta.",
    p_delta=Decimal("0.01"),
    g_delta=Decimal("0.02"),
    o_delta=Decimal("0.03"),
    r_delta=Decimal("0.04"),
    e_delta=Decimal("0.05"),
    confidence=None,
    assessed_at=datetime.now(UTC),
    assessed_by=ACTOR,
    methodology_version="observed-pgor-delta-v1",
    version=1,
)


class _Transaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, _exc_type, _exc, _tb):
        return False


class _Session:
    def begin(self):
        return _Transaction()


class _OutcomeRepository:
    async def get(self, outcome_id):
        return BASE_OUTCOME if outcome_id == OUTCOME_ID else None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("target_status", "action", "classification"),
    [
        (
            OutcomeStatus.CONFIRMED,
            HumanDecisionAction.CONFIRM,
            OutcomeClassification.PROGRESS,
        ),
        (
            OutcomeStatus.MODIFIED,
            HumanDecisionAction.MODIFY,
            OutcomeClassification.PROGRESS,
        ),
        (
            OutcomeStatus.NEEDS_MORE_TIME,
            HumanDecisionAction.DEFER,
            OutcomeClassification.NEEDS_MORE_TIME,
        ),
        (
            OutcomeStatus.NEEDS_MORE_DATA,
            HumanDecisionAction.DEFER,
            OutcomeClassification.NEEDS_MORE_DATA,
        ),
    ],
)
async def test_every_human_outcome_disposition_finalizes_reassessment_and_signals_temporal(
    monkeypatch,
    target_status,
    action,
    classification,
) -> None:
    calls = {}
    completed_plan = SimpleNamespace(workflow_id="reassessment:test")
    settings = object()

    class _ReviewHandler:
        def __init__(self, **_kwargs):
            pass

        async def handle(self, command, *, action, target_status):
            calls["review_action"] = action
            calls["review_status"] = target_status
            updated = replace(
                BASE_OUTCOME,
                status=target_status,
                classification=command.classification,
                latest_human_decision_id=HUMAN_DECISION,
                reviewed_at=datetime.now(UTC),
                reviewed_by=ACTOR,
                version=2,
            )
            return (
                updated,
                SimpleNamespace(id=HUMAN_DECISION),
                SimpleNamespace(id=LEARNING_SIGNAL),
            )

    class _FinalizeHandler:
        def __init__(self, **_kwargs):
            pass

        async def handle(self, **kwargs):
            calls["finalize"] = kwargs
            return completed_plan

    async def _allow_assignment(**_kwargs):
        return None

    async def _signal(*, plan, settings):
        calls["signal_plan"] = plan
        calls["signal_settings"] = settings
        return True

    monkeypatch.setattr(routes, "SqlAlchemyOutcomeRepository", lambda _session: _OutcomeRepository())
    monkeypatch.setattr(routes, "ReviewOutcomeHandler", _ReviewHandler)
    monkeypatch.setattr(routes, "FinalizeOutcomeReviewHandler", _FinalizeHandler)
    monkeypatch.setattr(routes, "require_household_assignment", _allow_assignment)
    monkeypatch.setattr(routes, "signal_outcome_reviewed_best_effort", _signal)
    monkeypatch.setattr(routes, "get_settings", lambda: settings)

    response = await routes._review(
        outcome_id=OUTCOME_ID,
        expected_version=1,
        classification=classification,
        observed_change_summary=None,
        reason_code=None,
        reason_text=None,
        action=action,
        target_status=target_status,
        context=SimpleNamespace(actor_id=ACTOR),
        session=_Session(),
    )

    assert response.data.learning_signal_id == LEARNING_SIGNAL
    assert calls["review_action"] is action
    assert calls["review_status"] is target_status
    assert calls["finalize"]["outcome_id"] == OUTCOME_ID
    assert calls["signal_plan"] is completed_plan
    assert calls["signal_settings"] is settings
