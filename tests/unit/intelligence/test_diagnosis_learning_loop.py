from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import JsonValue

from hamoon.domains.intelligence.application.diagnosis_commands import (
    ReviewDiagnosisCommand,
)
from hamoon.domains.intelligence.application.diagnosis_handlers import (
    ReviewDiagnosisHandler,
)
from hamoon.domains.intelligence.domain.decisions import (
    AIDecision,
    AIDecisionStatus,
    AIDecisionType,
    DecisionTrace,
    Diagnosis,
    DiagnosisStatus,
    HumanDecision,
    HumanDecisionAction,
    LearningSignal,
)
from hamoon.domains.operations.domain.entities import (
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)
from hamoon.infrastructure.ai.diagnosis_runtime import DIAGNOSIS_V1_SCHEMA

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD_ID = UUID("22222222-2222-2222-2222-222222222222")
ASSESSMENT_ID = UUID("33333333-3333-3333-3333-333333333333")
PACKAGE_ID = UUID("44444444-4444-4444-4444-444444444444")
SNAPSHOT_ID = UUID("55555555-5555-5555-5555-555555555555")
AI_DECISION_ID = UUID("66666666-6666-6666-6666-666666666666")
DIAGNOSIS_ID = UUID("77777777-7777-7777-7777-777777777777")
TRACE_ID = UUID("88888888-8888-8888-8888-888888888888")

MACHINE_OUTPUT: dict[str, JsonValue] = {
    "schema_version": "diagnosis-v1",
    "summary": "Machine proposal",
    "items": [
        {
            "code": "PGOR_BOTTLENECK_O",
            "category": "NEED",
            "title": "Opportunity constraint",
            "rationale": "O is the current bottleneck.",
            "supporting_feature_refs": ["pgor.bottleneck_variables"],
            "uncertainty": "LOW",
        }
    ],
    "review_flags": ["HUMAN_REVIEW_REQUIRED"],
}


class DiagnosisRepo:
    def __init__(self) -> None:
        self.item = Diagnosis(
            id=DIAGNOSIS_ID,
            household_id=HOUSEHOLD_ID,
            ai_decision_id=AI_DECISION_ID,
            status=DiagnosisStatus.UNDER_REVIEW,
            version=1,
            accepted_payload=None,
            created_at=datetime.now(UTC),
        )

    async def add(self, diagnosis: Diagnosis) -> None:
        self.item = diagnosis

    async def get(self, diagnosis_id: UUID):
        return self.item if diagnosis_id == self.item.id else None

    async def update(self, diagnosis: Diagnosis, *, expected_version: int) -> None:
        assert self.item.version == expected_version
        self.item = diagnosis


class AIDecisionRepo:
    async def add(self, decision: AIDecision) -> None:
        raise AssertionError("not used")

    async def get(self, decision_id: UUID):
        if decision_id != AI_DECISION_ID:
            return None
        return AIDecision(
            id=AI_DECISION_ID,
            household_id=HOUSEHOLD_ID,
            assessment_id=ASSESSMENT_ID,
            feature_package_id=PACKAGE_ID,
            pgor_snapshot_id=SNAPSHOT_ID,
            decision_type=AIDecisionType.DIAGNOSIS,
            status=AIDecisionStatus.GENERATED,
            provider_code="FAKE",
            model_id="fake-v1",
            model_alias="hamoon.diagnosis.v1",
            routing_policy_id=UUID("99999999-9999-9999-9999-999999999999"),
            routing_policy_version="local-test-v1",
            prompt_policy_version="diagnosis-prompt-v1",
            output_schema_version="diagnosis-v1",
            structured_output=MACHINE_OUTPUT,
            trace_id=TRACE_ID,
            generated_at=datetime.now(UTC),
        )


class FeaturePackageRepo:
    async def add(self, package) -> None:
        raise AssertionError("not used")

    async def get(self, package_id: UUID):
        if package_id != PACKAGE_ID:
            return None

        class Package:
            def provider_payload(self):
                return {"pgor.bottleneck_variables": ["O"]}

        return Package()

    async def get_by_snapshot(self, *, snapshot_id: UUID, schema_version: str):
        return None


class HumanDecisionRepo:
    def __init__(self) -> None:
        self.items: list[HumanDecision] = []

    async def add(self, decision: HumanDecision) -> None:
        self.items.append(decision)


class TraceRepo:
    def __init__(self) -> None:
        self.item = DecisionTrace(
            id=TRACE_ID,
            household_id=HOUSEHOLD_ID,
            trace_type=AIDecisionType.DIAGNOSIS,
            state_fingerprint="a" * 64,
            pgor_snapshot_id=SNAPSHOT_ID,
            feature_package_id=PACKAGE_ID,
            ai_decision_id=AI_DECISION_ID,
            opened_at=datetime.now(UTC),
        )

    async def add(self, trace: DecisionTrace) -> None:
        self.item = trace

    async def get_by_ai_decision(self, ai_decision_id: UUID):
        return self.item if ai_decision_id == self.item.ai_decision_id else None

    async def attach_human_decision(
        self,
        *,
        ai_decision_id: UUID,
        human_decision_id: UUID,
        learning_signal_id: UUID | None = None,
        closed_at=None,
    ) -> None:
        assert ai_decision_id == self.item.ai_decision_id
        self.item = DecisionTrace(
            id=self.item.id,
            household_id=self.item.household_id,
            trace_type=self.item.trace_type,
            state_fingerprint=self.item.state_fingerprint,
            pgor_snapshot_id=self.item.pgor_snapshot_id,
            feature_package_id=self.item.feature_package_id,
            ai_decision_id=self.item.ai_decision_id,
            human_decision_id=human_decision_id,
            opened_at=self.item.opened_at,
            closed_at=closed_at,
            learning_signal_id=learning_signal_id,
        )


class LearningRepo:
    def __init__(self) -> None:
        self.items: list[LearningSignal] = []

    async def add(self, signal: LearningSignal) -> None:
        self.items.append(signal)


class WorkItems:
    def __init__(self) -> None:
        self.item = WorkItem(
            id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            household_id=HOUSEHOLD_ID,
            work_type=WorkItemType.DIAGNOSIS_REVIEW,
            resource_type="DIAGNOSIS",
            resource_id=DIAGNOSIS_ID,
            title="review",
            reason="human review required",
            priority=70,
            status=WorkItemStatus.OPEN,
            version=1,
            due_at=None,
            assigned_actor_id=None,
            policy_version="diagnosis-review-v1",
            created_at=datetime.now(UTC),
            created_by=ACTOR_ID,
        )

    async def get_by_resource(
        self,
        *,
        work_type: WorkItemType,
        resource_type: str,
        resource_id: UUID,
    ) -> WorkItem | None:
        if (
            work_type is self.item.work_type
            and resource_type == self.item.resource_type
            and resource_id == self.item.resource_id
        ):
            return self.item
        return None

    async def update(self, item: WorkItem, *, expected_version: int) -> None:
        assert self.item.version == expected_version
        self.item = item


class EventRecorder:
    def __init__(self) -> None:
        self.items = []

    async def record(self, event) -> None:
        self.items.append(event)


class AuditRecorder:
    def __init__(self) -> None:
        self.items = []

    async def record(self, audit) -> None:
        self.items.append(audit)


@pytest.mark.asyncio
async def test_confirm_preserves_machine_output_and_creates_learning_signal() -> None:
    diagnoses = DiagnosisRepo()
    humans = HumanDecisionRepo()
    traces = TraceRepo()
    learning = LearningRepo()
    events = EventRecorder()
    audits = AuditRecorder()
    work_items = WorkItems()

    updated, human, signal = await ReviewDiagnosisHandler(
        diagnoses=diagnoses,
        ai_decisions=AIDecisionRepo(),
        human_decisions=humans,
        feature_packages=FeaturePackageRepo(),
        traces=traces,
        learning_signals=learning,
        work_items=work_items,
        events=events,
        audits=audits,
        output_schema=DIAGNOSIS_V1_SCHEMA,
    ).handle(
        ReviewDiagnosisCommand(
            diagnosis_id=DIAGNOSIS_ID,
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

    assert updated.status is DiagnosisStatus.CONFIRMED
    assert updated.accepted_payload == MACHINE_OUTPUT
    assert human.accepted_payload == MACHINE_OUTPUT
    assert signal.signal_type.value == "DIAGNOSIS_CONFIRMED"
    assert [item.event_type for item in events.items] == [
        "DiagnosisConfirmed",
        "WorkItemCompleted",
    ]
    assert traces.item.closed_at is not None
    assert traces.item.learning_signal_id == signal.id
    assert work_items.item.status is WorkItemStatus.COMPLETED
    assert work_items.item.completed_by == ACTOR_ID


@pytest.mark.asyncio
async def test_modify_keeps_human_payload_separate_from_machine_proposal() -> None:
    modified = dict(MACHINE_OUTPUT)
    modified["summary"] = "Human-adjusted diagnosis"

    diagnoses = DiagnosisRepo()
    humans = HumanDecisionRepo()
    traces = TraceRepo()
    learning = LearningRepo()

    updated, human, signal = await ReviewDiagnosisHandler(
        diagnoses=diagnoses,
        ai_decisions=AIDecisionRepo(),
        human_decisions=humans,
        feature_packages=FeaturePackageRepo(),
        traces=traces,
        learning_signals=learning,
        events=EventRecorder(),
        audits=AuditRecorder(),
        output_schema=DIAGNOSIS_V1_SCHEMA,
    ).handle(
        ReviewDiagnosisCommand(
            diagnosis_id=DIAGNOSIS_ID,
            actor_id=ACTOR_ID,
            action=HumanDecisionAction.MODIFY,
            expected_version=1,
            reason_code="CASEWORKER_JUDGMENT",
            reason_text="Field evidence changes the summary.",
            modified_payload=modified,
            request_id="req-2",
            correlation_id="corr-2",
        )
    )

    machine = await AIDecisionRepo().get(AI_DECISION_ID)
    assert machine is not None
    assert machine.structured_output["summary"] == "Machine proposal"
    assert updated.accepted_payload == modified
    assert human.modified_payload == modified
    assert signal.signal_type.value == "DIAGNOSIS_MODIFIED"
