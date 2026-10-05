from datetime import UTC, datetime
from uuid import UUID

import pytest

from hamoon.domains.intelligence.domain.decisions import (
    AIDecision,
    AIDecisionStatus,
    AIDecisionType,
    DecisionTrace,
    HumanDecision,
    HumanDecisionAction,
    LearningSignal,
)
from hamoon.domains.intelligence.domain.entities import (
    FeaturePackage,
    FeaturePackageType,
    FeatureValue,
)
from hamoon.domains.intervention.application.commands import ActivateInterventionCommand
from hamoon.domains.intervention.application.handlers import ActivateInterventionHandler
from hamoon.domains.intervention.domain.entities import Intervention
from hamoon.domains.prescription.application.commands import ReviewPrescriptionCommand
from hamoon.domains.prescription.application.review import ReviewPrescriptionHandler
from hamoon.domains.prescription.domain.entities import Prescription, PrescriptionStatus
from hamoon.infrastructure.ai.prescription_runtime import PRESCRIPTION_V1_SCHEMA

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD_ID = UUID("22222222-2222-2222-2222-222222222222")
ASSESSMENT_ID = UUID("33333333-3333-3333-3333-333333333333")
SNAPSHOT_ID = UUID("44444444-4444-4444-4444-444444444444")
DIAGNOSIS_ID = UUID("55555555-5555-5555-5555-555555555555")
PRESCRIPTION_ID = UUID("66666666-6666-6666-6666-666666666666")
AI_DECISION_ID = UUID("77777777-7777-7777-7777-777777777777")
FEATURE_ID = UUID("88888888-8888-8888-8888-888888888888")
TRACE_ID = UUID("99999999-9999-9999-9999-999999999999")

OUTPUT = {
    "schema_version": "prescription-v1",
    "summary": "Opportunity-targeted proposal.",
    "intensity_score": "0.54",
    "items": [
        {
            "code": "O_MARKET_LINKAGE",
            "target_variable": "O",
            "intervention_type": "MARKET_LINKAGE",
            "priority_rank": 1,
            "title": "Connect to market",
            "rationale": "O is the current bottleneck.",
            "success_criteria": ["Opportunity is reassessed."],
            "review_schedule": {
                "review_after_days": 90,
                "rationale": "Three-month follow-up.",
            },
            "diagnosis_refs": [f"diagnosis:{DIAGNOSIS_ID}"],
            "supporting_feature_refs": [
                "pgor.bottleneck_variables",
                "prescription.intensity_score",
                "diagnosis.accepted_payload",
            ],
        }
    ],
    "review_flags": ["HUMAN_REVIEW_REQUIRED"],
}


class PrescriptionRepo:
    def __init__(self) -> None:
        self.item = Prescription(
            id=PRESCRIPTION_ID,
            household_id=HOUSEHOLD_ID,
            diagnosis_id=DIAGNOSIS_ID,
            ai_decision_id=AI_DECISION_ID,
            pgor_snapshot_id=SNAPSHOT_ID,
            status=PrescriptionStatus.UNDER_REVIEW,
            version=1,
            accepted_payload=None,
            created_at=datetime.now(UTC),
            created_by=ACTOR_ID,
        )
        self.items = []

    async def add(self, prescription) -> None:
        self.item = prescription

    async def get(self, prescription_id):
        return self.item if prescription_id == self.item.id else None

    async def update(self, prescription, *, expected_version):
        assert self.item.version == expected_version
        self.item = prescription

    async def add_items(self, items):
        self.items.extend(items)

    async def get_item(self, *, prescription_id, item_id):
        return next(
            (
                item
                for item in self.items
                if item.prescription_id == prescription_id and item.id == item_id
            ),
            None,
        )

    async def list_items(self, prescription_id):
        return [item for item in self.items if item.prescription_id == prescription_id]

    async def mark_item_activated(self, item_id):
        from dataclasses import replace
        from hamoon.domains.prescription.domain.entities import PrescriptionItemStatus

        self.items = [
            replace(item, status=PrescriptionItemStatus.ACTIVATED)
            if item.id == item_id
            else item
            for item in self.items
        ]


class AIDecisionRepo:
    async def get(self, decision_id):
        if decision_id != AI_DECISION_ID:
            return None
        return AIDecision(
            id=AI_DECISION_ID,
            household_id=HOUSEHOLD_ID,
            assessment_id=ASSESSMENT_ID,
            feature_package_id=FEATURE_ID,
            pgor_snapshot_id=SNAPSHOT_ID,
            decision_type=AIDecisionType.PRESCRIPTION,
            status=AIDecisionStatus.GENERATED,
            provider_code="FAKE",
            model_id="fake",
            model_alias="hamoon.prescription.v1",
            routing_policy_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            routing_policy_version="test",
            prompt_policy_version="test",
            output_schema_version="prescription-v1",
            structured_output=OUTPUT,
            trace_id=TRACE_ID,
            generated_at=datetime.now(UTC),
        )

    async def add(self, decision):
        raise AssertionError("not used")


class FeatureRepo:
    async def get(self, package_id):
        if package_id != FEATURE_ID:
            return None
        return FeaturePackage(
            id=FEATURE_ID,
            household_id=HOUSEHOLD_ID,
            assessment_id=ASSESSMENT_ID,
            pgor_snapshot_id=SNAPSHOT_ID,
            package_type=FeaturePackageType.PRESCRIPTION,
            schema_version="prescription-input-v1",
            source_fingerprint="a" * 64,
            data_quality_flags=(),
            values=(
                FeatureValue(
                    "pgor.bottleneck_variables",
                    ["O"],
                    (f"pgor_snapshot:{SNAPSHOT_ID}",),
                ),
                FeatureValue(
                    "prescription.intensity_score",
                    "0.54",
                    (f"pgor_snapshot:{SNAPSHOT_ID}",),
                ),
                FeatureValue(
                    "diagnosis.id",
                    str(DIAGNOSIS_ID),
                    (f"diagnosis:{DIAGNOSIS_ID}",),
                ),
                FeatureValue(
                    "diagnosis.accepted_payload",
                    {"summary": "Opportunity bottleneck"},
                    (f"diagnosis:{DIAGNOSIS_ID}",),
                ),
            ),
            created_at=datetime.now(UTC),
            created_by=ACTOR_ID,
        )

    async def add(self, package):
        raise AssertionError("not used")

    async def get_by_snapshot(self, *, snapshot_id, schema_version):
        return None


class HumanRepo:
    def __init__(self):
        self.items: list[HumanDecision] = []

    async def add(self, decision):
        self.items.append(decision)

    async def get(self, decision_id):
        return next((item for item in self.items if item.id == decision_id), None)


class LearningRepo:
    def __init__(self):
        self.items: list[LearningSignal] = []

    async def add(self, signal):
        self.items.append(signal)


class TraceRepo:
    def __init__(self):
        self.trace = DecisionTrace(
            id=TRACE_ID,
            household_id=HOUSEHOLD_ID,
            trace_type=AIDecisionType.PRESCRIPTION,
            state_fingerprint="a" * 64,
            pgor_snapshot_id=SNAPSHOT_ID,
            feature_package_id=FEATURE_ID,
            ai_decision_id=AI_DECISION_ID,
            opened_at=datetime.now(UTC),
            prescription_id=PRESCRIPTION_ID,
        )
        self.intervention_id = None

    async def add(self, trace):
        self.trace = trace

    async def get_by_ai_decision(self, ai_decision_id):
        return self.trace

    async def attach_human_decision(
        self,
        *,
        ai_decision_id,
        human_decision_id,
        learning_signal_id=None,
        closed_at=None,
    ):
        assert ai_decision_id == AI_DECISION_ID
        self.trace = DecisionTrace(
            id=self.trace.id,
            household_id=self.trace.household_id,
            trace_type=self.trace.trace_type,
            state_fingerprint=self.trace.state_fingerprint,
            pgor_snapshot_id=self.trace.pgor_snapshot_id,
            feature_package_id=self.trace.feature_package_id,
            ai_decision_id=self.trace.ai_decision_id,
            human_decision_id=human_decision_id,
            opened_at=self.trace.opened_at,
            closed_at=closed_at,
            prescription_id=self.trace.prescription_id,
            learning_signal_id=learning_signal_id,
        )

    async def attach_intervention(self, *, ai_decision_id, intervention_id):
        assert ai_decision_id == AI_DECISION_ID
        self.intervention_id = intervention_id


class InterventionRepo:
    def __init__(self):
        self.item: Intervention | None = None

    async def add(self, intervention):
        self.item = intervention

    async def get(self, intervention_id):
        return self.item if self.item and self.item.id == intervention_id else None

    async def get_by_prescription_item(self, prescription_item_id):
        if self.item and self.item.prescription_item_id == prescription_item_id:
            return self.item
        return None

    async def list_for_household(self, household_id):
        return [self.item] if self.item and self.item.household_id == household_id else []


class Recorder:
    def __init__(self):
        self.items = []

    async def record(self, item):
        self.items.append(item)


@pytest.mark.asyncio
async def test_approve_prescription_materializes_accepted_item_and_learning_signal() -> None:
    prescriptions = PrescriptionRepo()
    learning = LearningRepo()
    events = Recorder()
    traces = TraceRepo()

    updated, human, signal, items = await ReviewPrescriptionHandler(
        prescriptions=prescriptions,
        ai_decisions=AIDecisionRepo(),
        feature_packages=FeatureRepo(),
        human_decisions=HumanRepo(),
        learning_signals=learning,
        traces=traces,
        events=events,
        audits=Recorder(),
        output_schema=PRESCRIPTION_V1_SCHEMA,
    ).handle(
        ReviewPrescriptionCommand(
            prescription_id=PRESCRIPTION_ID,
            actor_id=ACTOR_ID,
            action=HumanDecisionAction.CONFIRM,
            expected_version=1,
            reason_code=None,
            reason_text=None,
            modified_payload=None,
            request_id="req-1",
            correlation_id="corr-1",
        )
    )

    assert updated.status is PrescriptionStatus.APPROVED
    assert human.decision_context.value == "PRESCRIPTION"
    assert signal.signal_type.value == "PRESCRIPTION_CONFIRMED"
    assert traces.trace.learning_signal_id == signal.id
    assert len(items) == 1
    assert items[0].target_pgor_variable.value == "O"
    assert items[0].intervention_type.value == "MARKET_LINKAGE"
    assert events.items[0].event_type == "PrescriptionApproved"
    assert events.items[1].event_type == "LearningSignalCreated"


@pytest.mark.asyncio
async def test_only_accepted_prescription_item_can_activate_intervention() -> None:
    prescriptions = PrescriptionRepo()
    review = ReviewPrescriptionHandler(
        prescriptions=prescriptions,
        ai_decisions=AIDecisionRepo(),
        feature_packages=FeatureRepo(),
        human_decisions=HumanRepo(),
        learning_signals=LearningRepo(),
        traces=TraceRepo(),
        events=Recorder(),
        audits=Recorder(),
        output_schema=PRESCRIPTION_V1_SCHEMA,
    )
    _, _, _, items = await review.handle(
        ReviewPrescriptionCommand(
            prescription_id=PRESCRIPTION_ID,
            actor_id=ACTOR_ID,
            action=HumanDecisionAction.CONFIRM,
            expected_version=1,
            reason_code=None,
            reason_text=None,
            modified_payload=None,
            request_id="req-2",
            correlation_id="corr-2",
        )
    )

    interventions = InterventionRepo()
    trace = TraceRepo()
    intervention = await ActivateInterventionHandler(
        prescriptions=prescriptions,
        interventions=interventions,
        traces=trace,
        events=Recorder(),
        audits=Recorder(),
    ).handle(
        ActivateInterventionCommand(
            prescription_id=PRESCRIPTION_ID,
            prescription_item_id=items[0].id,
            actor_id=ACTOR_ID,
            request_id="req-3",
            correlation_id="corr-3",
        )
    )

    assert intervention.status.value == "ACTIVE"
    assert intervention.target_pgor_variable.value == "O"
    assert intervention.intervention_type.value == "MARKET_LINKAGE"
    assert trace.intervention_id == intervention.id
