from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from hamoon.domains.intelligence.application.diagnosis_commands import (
    GenerateDiagnosisCommand,
)
from hamoon.domains.intelligence.application.diagnosis_handlers import (
    GenerateDiagnosisHandler,
)
from hamoon.domains.intelligence.domain.decisions import (
    AIDecision,
    AIExecutionResult,
    DecisionTrace,
    Diagnosis,
    DiagnosisStatus,
)
from hamoon.domains.intelligence.domain.entities import (
    FeaturePackage,
    FeaturePackageType,
    FeatureValue,
)
from hamoon.domains.intelligence.domain.errors import DiagnosisGenerationError
from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.pgor.domain.engine import (
    EBand,
    PBand,
    PGORSnapshotStatus,
    RBand,
)
from hamoon.domains.pgor.domain.snapshots import PGORSnapshot
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD_ID = UUID("22222222-2222-2222-2222-222222222222")
ASSESSMENT_ID = UUID("33333333-3333-3333-3333-333333333333")
SNAPSHOT_ID = UUID("44444444-4444-4444-4444-444444444444")
DEFINITION_ID = UUID("55555555-5555-5555-5555-555555555555")
FORMULA_ID = UUID("66666666-6666-6666-6666-666666666666")
PACKAGE_ID = UUID("77777777-7777-7777-7777-777777777777")
ROUTING_ID = UUID("88888888-8888-8888-8888-888888888888")


class SnapshotRepo:
    async def get(self, snapshot_id: UUID):
        if snapshot_id != SNAPSHOT_ID:
            return None
        return PGORSnapshot(
            id=SNAPSHOT_ID,
            household_id=HOUSEHOLD_ID,
            assessment_id=ASSESSMENT_ID,
            definition_version_id=DEFINITION_ID,
            formula_version_id=FORMULA_ID,
            engine_version="1.0.0",
            scoring_version="raw-0-100-v1",
            status=PGORSnapshotStatus.OFFICIAL,
            p=Decimal("0.6"),
            g=Decimal("0.7"),
            o=Decimal("0.3"),
            r=Decimal("0.5"),
            e=Decimal("0.4"),
            bottleneck_variables=(PGORVariableCode.O,),
            e_band=EBand.SUPPORTED_EMPOWERMENT,
            p_band=PBand.MEDIUM,
            r_band=RBand.ACCEPTABLE,
            completeness_ratio=Decimal("1"),
            data_quality_flags=(),
            input_fingerprint="a" * 64,
            calculated_at=datetime.now(UTC),
            calculated_by=ACTOR_ID,
        )

    async def list_inputs(self, snapshot_id: UUID):
        raise AssertionError("existing feature package should be reused")

    async def create(self, **kwargs):
        raise AssertionError("not used")


class DefinitionRepo:
    async def get_bundle(self, definition_version_id: UUID):
        raise AssertionError("existing feature package should be reused")

    async def get_active_bundle(self):
        return None

    async def get_version(self, definition_version_id: UUID):
        return None

    async def list_indicators(self, definition_version_id: UUID):
        return []

    async def get_indicator(self, **kwargs):
        return None


class FeatureRepo:
    def __init__(self) -> None:
        self.package = FeaturePackage(
            id=PACKAGE_ID,
            household_id=HOUSEHOLD_ID,
            assessment_id=ASSESSMENT_ID,
            pgor_snapshot_id=SNAPSHOT_ID,
            package_type=FeaturePackageType.DIAGNOSIS,
            schema_version="diagnosis-input-v1",
            source_fingerprint="b" * 64,
            data_quality_flags=(),
            values=(
                FeatureValue(
                    key="pgor.bottleneck_variables",
                    value=["O"],
                    source_refs=(f"pgor_snapshot:{SNAPSHOT_ID}",),
                ),
            ),
            created_at=datetime.now(UTC),
            created_by=ACTOR_ID,
        )

    async def add(self, package: FeaturePackage) -> None:
        self.package = package

    async def get(self, package_id: UUID):
        return self.package if package_id == PACKAGE_ID else None

    async def get_by_snapshot(self, *, snapshot_id: UUID, schema_version: str):
        if snapshot_id == SNAPSHOT_ID and schema_version == "diagnosis-input-v1":
            return self.package
        return None


class AIClient:
    def __init__(self, *, grounded: bool = True) -> None:
        self.grounded = grounded

    async def generate_diagnosis(self, *, feature_package, correlation_id: str):
        ref = "pgor.bottleneck_variables" if self.grounded else "missing.feature"
        return AIExecutionResult(
            provider_code="FAKE",
            model_id="fake-diagnosis-v1",
            model_alias="hamoon.diagnosis.v1",
            routing_policy_id=ROUTING_ID,
            routing_policy_version="test-v1",
            prompt_policy_version="diagnosis-prompt-v1",
            output_schema_version="diagnosis-v1",
            output={
                "schema_version": "diagnosis-v1",
                "summary": "Opportunity is the current bottleneck.",
                "items": [
                    {
                        "code": "PGOR_BOTTLENECK_O",
                        "category": "NEED",
                        "title": "Opportunity constraint",
                        "rationale": "O is the minimum PGOR variable.",
                        "supporting_feature_refs": [ref],
                        "uncertainty": "LOW",
                    }
                ],
                "review_flags": ["HUMAN_REVIEW_REQUIRED"],
            },
        )


class AIDecisionRepo:
    def __init__(self) -> None:
        self.item: AIDecision | None = None

    async def add(self, decision: AIDecision) -> None:
        self.item = decision

    async def get(self, decision_id: UUID):
        return self.item if self.item is not None and self.item.id == decision_id else None


class DiagnosisRepo:
    def __init__(self) -> None:
        self.item: Diagnosis | None = None

    async def add(self, diagnosis: Diagnosis) -> None:
        self.item = diagnosis

    async def get(self, diagnosis_id: UUID):
        return self.item if self.item is not None and self.item.id == diagnosis_id else None

    async def update(self, diagnosis: Diagnosis, *, expected_version: int) -> None:
        raise AssertionError("not used")


class TraceRepo:
    def __init__(self) -> None:
        self.item: DecisionTrace | None = None

    async def add(self, trace: DecisionTrace) -> None:
        self.item = trace

    async def get_by_ai_decision(self, ai_decision_id: UUID):
        return self.item

    async def attach_human_decision(self, **kwargs) -> None:
        raise AssertionError("not used")


class AcceptedStateRepo:
    def __init__(self, version: int = 7) -> None:
        self.version = version

    async def context_version(self, household_id: UUID) -> int:
        assert household_id == HOUSEHOLD_ID
        return self.version


class EventRecorder:
    def __init__(self) -> None:
        self.items: list[DomainEventRecord] = []

    async def record(self, event: DomainEventRecord) -> None:
        self.items.append(event)


class AuditRecorder:
    def __init__(self) -> None:
        self.items: list[AuditRecord] = []

    async def record(self, audit: AuditRecord) -> None:
        self.items.append(audit)


@pytest.mark.asyncio
async def test_generate_diagnosis_persists_ai_proposal_and_open_trace() -> None:
    decisions = AIDecisionRepo()
    diagnoses = DiagnosisRepo()
    traces = TraceRepo()
    events = EventRecorder()

    accepted_state = AcceptedStateRepo()
    diagnosis, decision = await GenerateDiagnosisHandler(
        snapshots=SnapshotRepo(),
        definitions=DefinitionRepo(),
        feature_packages=FeatureRepo(),
        ai_decisions=decisions,
        diagnoses=diagnoses,
        traces=traces,
        ai_client=AIClient(),
        accepted_state=accepted_state,
        events=events,
        audits=AuditRecorder(),
    ).handle(
        GenerateDiagnosisCommand(
            household_id=HOUSEHOLD_ID,
            pgor_snapshot_id=SNAPSHOT_ID,
            actor_id=ACTOR_ID,
            request_id="req-1",
            correlation_id="corr-1",
        )
    )

    assert diagnosis.status is DiagnosisStatus.UNDER_REVIEW
    assert diagnosis.accepted_payload is None
    assert decision.structured_output["schema_version"] == "diagnosis-v1"
    assert decision.feature_package_id == PACKAGE_ID
    assert traces.item is not None
    assert traces.item.human_decision_id is None
    assert traces.item.household_context_version == 7
    assert traces.item.closed_at is None
    assert events.items[-1].event_type == "DiagnosisGenerated"


@pytest.mark.asyncio
async def test_generate_diagnosis_rejects_ungrounded_model_output() -> None:
    with pytest.raises(DiagnosisGenerationError, match="AI_OUTPUT_GROUNDING_FAILED"):
        await GenerateDiagnosisHandler(
            snapshots=SnapshotRepo(),
            definitions=DefinitionRepo(),
            feature_packages=FeatureRepo(),
            ai_decisions=AIDecisionRepo(),
            diagnoses=DiagnosisRepo(),
            traces=TraceRepo(),
            ai_client=AIClient(grounded=False),
            events=EventRecorder(),
            audits=AuditRecorder(),
        ).handle(
            GenerateDiagnosisCommand(
                household_id=HOUSEHOLD_ID,
                pgor_snapshot_id=SNAPSHOT_ID,
                actor_id=ACTOR_ID,
                request_id="req-2",
                correlation_id="corr-2",
            )
        )


@pytest.mark.asyncio
async def test_generate_diagnosis_rejects_stale_household_context() -> None:
    accepted_state = AcceptedStateRepo(version=11)
    handler = GenerateDiagnosisHandler(
        snapshots=SnapshotRepo(),
        definitions=DefinitionRepo(),
        feature_packages=FeatureRepo(),
        ai_decisions=AIDecisionRepo(),
        diagnoses=DiagnosisRepo(),
        traces=TraceRepo(),
        ai_client=AIClient(),
        accepted_state=accepted_state,
        events=EventRecorder(),
        audits=AuditRecorder(),
    )
    command = GenerateDiagnosisCommand(
        household_id=HOUSEHOLD_ID,
        pgor_snapshot_id=SNAPSHOT_ID,
        actor_id=ACTOR_ID,
        request_id="req-stale",
        correlation_id="corr-stale",
    )
    prepared = await handler.prepare(command)
    accepted_state.version = 12
    result = await handler.infer(
        prepared=prepared,
        correlation_id="corr-stale",
    )

    with pytest.raises(
        DiagnosisGenerationError,
        match="HOUSEHOLD_CONTEXT_VERSION_CONFLICT",
    ):
        await handler.persist(
            command=command,
            prepared=prepared,
            result=result,
        )
