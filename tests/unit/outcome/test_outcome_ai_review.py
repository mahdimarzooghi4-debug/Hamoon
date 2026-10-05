from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from hamoon.domains.intelligence.domain.decisions import (
    AIDecision,
    AIDecisionStatus,
    AIDecisionType,
    HumanDecisionAction,
)
from hamoon.domains.outcome.application.commands import ReviewOutcomeCommand
from hamoon.domains.outcome.application.handlers import ReviewOutcomeHandler
from hamoon.domains.outcome.domain.entities import (
    HamoonOutcome,
    OutcomeClassification,
    OutcomeInterpretationProposal,
    OutcomeStatus,
)

ACTOR = UUID("11111111-1111-1111-1111-111111111111")
HH = UUID("22222222-2222-2222-2222-222222222222")
OUTCOME = UUID("33333333-3333-3333-3333-333333333333")
AI = UUID("44444444-4444-4444-4444-444444444444")
RESULT = UUID("55555555-5555-5555-5555-555555555555")


class Outcomes:
    def __init__(self):
        self.item = HamoonOutcome(
            id=OUTCOME,
            household_id=HH,
            intervention_id=ACTOR,
            referral_id=None,
            provider_result_id=RESULT,
            pre_assessment_id=ACTOR,
            post_assessment_id=AI,
            pre_pgor_snapshot_id=ACTOR,
            post_pgor_snapshot_id=AI,
            status=OutcomeStatus.UNDER_REVIEW,
            classification=None,
            observed_change_summary="deterministic delta",
            p_delta=Decimal("0"),
            g_delta=Decimal("0"),
            o_delta=Decimal("0.1"),
            r_delta=Decimal("0"),
            e_delta=Decimal("0.05"),
            confidence=None,
            assessed_at=datetime.now(UTC),
            assessed_by=ACTOR,
            methodology_version="observed-pgor-delta-v1",
            version=1,
        )

    async def get(self, outcome_id):
        return self.item if outcome_id == OUTCOME else None

    async def update(self, outcome, *, expected_version):
        assert self.item.version == expected_version
        self.item = outcome


class Proposals:
    async def get_by_outcome(self, outcome_id):
        if outcome_id != OUTCOME:
            return None
        return OutcomeInterpretationProposal(ACTOR, OUTCOME, AI, datetime.now(UTC))


class Decisions:
    async def get(self, decision_id):
        if decision_id != AI:
            return None
        return AIDecision(
            id=AI,
            household_id=HH,
            assessment_id=ACTOR,
            feature_package_id=ACTOR,
            pgor_snapshot_id=ACTOR,
            decision_type=AIDecisionType.OUTCOME_INTERPRETATION,
            status=AIDecisionStatus.GENERATED,
            provider_code="FAKE",
            model_id="fake",
            model_alias="hamoon.outcome.v1",
            routing_policy_id=ACTOR,
            routing_policy_version="v1",
            prompt_policy_version="v1",
            output_schema_version="outcome-interpretation-v1",
            structured_output={
                "schema_version": "outcome-interpretation-v1",
                "classification": "PROGRESS",
                "observed_change_summary": "Machine proposal.",
                "causal_claim": False,
                "supporting_feature_refs": ["pgor.delta.E"],
                "review_flags": ["HUMAN_REVIEW_REQUIRED"],
            },
            trace_id=ACTOR,
            generated_at=datetime.now(UTC),
        )


class Store:
    def __init__(self):
        self.items = []

    async def add(self, item):
        self.items.append(item)


class Traces:
    def __init__(self):
        self.closed = None

    async def attach_human_decision(self, **kwargs):
        self.closed = kwargs


class Recorder:
    async def record(self, item):
        pass


@pytest.mark.asyncio
async def test_confirm_links_human_decision_learning_signal_and_trace_to_ai() -> None:
    traces = Traces()
    updated, decision, signal = await ReviewOutcomeHandler(
        outcomes=Outcomes(),
        human_decisions=Store(),
        learning_signals=Store(),
        events=Recorder(),
        audits=Recorder(),
        proposals=Proposals(),
        ai_decisions=Decisions(),
        traces=traces,
    ).handle(
        ReviewOutcomeCommand(
            outcome_id=OUTCOME,
            expected_version=1,
            classification=OutcomeClassification.PROGRESS,
            observed_change_summary=None,
            reason_code=None,
            reason_text=None,
            actor_id=ACTOR,
            request_id="req",
            correlation_id="corr",
        ),
        action=HumanDecisionAction.CONFIRM,
        target_status=OutcomeStatus.CONFIRMED,
    )
    assert updated.observed_change_summary == "Machine proposal."
    assert decision.ai_decision_id == AI
    assert decision.outcome_id == OUTCOME
    assert decision.accepted_payload is not None
    assert decision.accepted_payload["causal_claim"] is False
    assert signal.ai_decision_id == AI
    assert signal.human_decision_id == decision.id
    assert signal.provider_result_id == RESULT
    assert signal.outcome_id == OUTCOME
    assert signal.outcome_id != signal.provider_result_id
    assert traces.closed["ai_decision_id"] == AI
    assert traces.closed["human_decision_id"] == decision.id
    assert traces.closed["learning_signal_id"] == signal.id
    assert traces.closed["closed_at"] is not None
