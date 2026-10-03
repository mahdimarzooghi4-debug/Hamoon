from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import JsonValue

from hamoon.domains.intelligence.domain.decisions import (
    AIDecision,
    AIDecisionStatus,
    AIDecisionType,
    AIExecutionResult,
    Diagnosis,
    DiagnosisStatus,
)
from hamoon.domains.intelligence.domain.entities import FeaturePackage
from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.pgor.domain.engine import (
    EBand,
    PBand,
    PGORSnapshotStatus,
    RBand,
)
from hamoon.domains.pgor.domain.snapshots import PGORSnapshot
from hamoon.domains.prescription.application.commands import GeneratePrescriptionCommand
from hamoon.domains.prescription.application.handlers import GeneratePrescriptionHandler
from hamoon.domains.prescription.domain.entities import Prescription
from hamoon.domains.prescription.domain.errors import PrescriptionGenerationError

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD_ID = UUID("22222222-2222-2222-2222-222222222222")
ASSESSMENT_ID = UUID("33333333-3333-3333-3333-333333333333")
SNAPSHOT_ID = UUID("44444444-4444-4444-4444-444444444444")
DIAGNOSIS_ID = UUID("55555555-5555-5555-5555-555555555555")
DIAGNOSIS_AI_ID = UUID("66666666-6666-6666-6666-666666666666")
FORMULA_ID = UUID("77777777-7777-7777-7777-777777777777")
DEFINITION_ID = UUID("88888888-8888-8888-8888-888888888888")


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
            p=Decimal("0.8"),
            g=Decimal("0.7"),
            o=Decimal("0.2"),
            r=Decimal("0.6"),
            e=Decimal("0.46"),
            bottleneck_variables=(PGORVariableCode.O,),
            e_band=EBand.SUPPORTED_EMPOWERMENT,
            p_band=PBand.DESIRABLE,
            r_band=RBand.ACCEPTABLE,
            completeness_ratio=Decimal("1"),
            data_quality_flags=(),
            input_fingerprint="a" * 64,
            calculated_at=datetime.now(UTC),
            calculated_by=ACTOR_ID,
        )

    async def list_inputs(self, snapshot_id: UUID):
        return []


class DiagnosisRepo:
    async def get(self, diagnosis_id: UUID):
        if diagnosis_id != DIAGNOSIS_ID:
            return None
        return Diagnosis(
            id=DIAGNOSIS_ID,
            household_id=HOUSEHOLD_ID,
            ai_decision_id=DIAGNOSIS_AI_ID,
            status=DiagnosisStatus.CONFIRMED,
            version=2,
            accepted_payload={
                "schema_version": "diagnosis-v1",
                "summary": "Opportunity is the bottleneck.",
                "items": [],
                "review_flags": ["HUMAN_REVIEW_REQUIRED"],
            },
            created_at=datetime.now(UTC),
        )


class AIDecisionRepo:
    def __init__(self) -> None:
        self.added: list[AIDecision] = []

    async def get(self, decision_id: UUID):
        if decision_id != DIAGNOSIS_AI_ID:
            return next((item for item in self.added if item.id == decision_id), None)
        return AIDecision(
            id=DIAGNOSIS_AI_ID,
            household_id=HOUSEHOLD_ID,
            assessment_id=ASSESSMENT_ID,
            feature_package_id=UUID("99999999-9999-9999-9999-999999999999"),
            pgor_snapshot_id=SNAPSHOT_ID,
            decision_type=AIDecisionType.DIAGNOSIS,
            status=AIDecisionStatus.GENERATED,
            provider_code="FAKE",
            model_id="fake",
            model_alias="hamoon.diagnosis.v1",
            routing_policy_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            routing_policy_version="test",
            prompt_policy_version="test",
            output_schema_version="diagnosis-v1",
            structured_output={},
            trace_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            generated_at=datetime.now(UTC),
        )

    async def add(self, decision: AIDecision) -> None:
        self.added.append(decision)


class FeatureRepo:
    def __init__(self) -> None:
        self.item: FeaturePackage | None = None

    async def add(self, package: FeaturePackage) -> None:
        self.item = package

    async def get(self, package_id: UUID):
        return self.item if self.item and self.item.id == package_id else None

    async def get_by_snapshot(self, *, snapshot_id: UUID, schema_version: str):
        if (
            self.item
            and self.item.pgor_snapshot_id == snapshot_id
            and self.item.schema_version == schema_version
        ):
            return self.item
        return None


class PrescriptionRepo:
    def __init__(self) -> None:
        self.item: Prescription | None = None

    async def add(self, prescription: Prescription) -> None:
        self.item = prescription

    async def get(self, prescription_id: UUID):
        return self.item if self.item and self.item.id == prescription_id else None


class TraceRepo:
    async def add(self, trace) -> None:
        self.item = trace

    async def get_by_ai_decision(self, ai_decision_id: UUID):
        return getattr(self, "item", None)

    async def attach_human_decision(self, **kwargs) -> None:
        raise AssertionError("not used")


class AIClient:
    def __init__(self, *, bad_target: bool = False) -> None:
        self.bad_target = bad_target

    async def generate_prescription(
        self,
        *,
        feature_package: FeaturePackage,
        correlation_id: str,
    ) -> AIExecutionResult:
        payload = feature_package.provider_payload()
        target = "P" if self.bad_target else "O"
        diagnosis_id = payload["diagnosis.id"]
        assert isinstance(diagnosis_id, str)
        return AIExecutionResult(
            provider_code="FAKE",
            model_id="fake-prescription-v1",
            model_alias="hamoon.prescription.v1",
            routing_policy_id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            routing_policy_version="test",
            prompt_policy_version="prescription-prompt-v1",
            output_schema_version="prescription-v1",
            output={
                "schema_version": "prescription-v1",
                "summary": "Opportunity-targeted proposal.",
                "intensity_score": payload["prescription.intensity_score"],
                "items": [
                    {
                        "code": "O_MARKET_LINKAGE",
                        "target_variable": target,
                        "intervention_type": "MARKET_LINKAGE",
                        "priority_rank": 1,
                        "title": "Connect to market",
                        "rationale": "O is the current bottleneck.",
                        "success_criteria": ["Opportunity score is reassessed."],
                        "review_schedule": {
                            "review_after_days": 90,
                            "rationale": "Follow-up proposal.",
                        },
                        "diagnosis_refs": [f"diagnosis:{diagnosis_id}"],
                        "supporting_feature_refs": [
                            "pgor.bottleneck_variables",
                            "prescription.intensity_score",
                            "diagnosis.accepted_payload",
                        ],
                    }
                ],
                "review_flags": ["HUMAN_REVIEW_REQUIRED"],
            },
        )


class Recorder:
    def __init__(self) -> None:
        self.items: list[object] = []

    async def record(self, item) -> None:
        self.items.append(item)


@pytest.mark.asyncio
async def test_prescription_generation_requires_accepted_diagnosis_and_targets_bottleneck() -> None:
    decisions = AIDecisionRepo()
    prescriptions = PrescriptionRepo()
    features = FeatureRepo()
    events = Recorder()
    audits = Recorder()
    handler = GeneratePrescriptionHandler(
        snapshots=SnapshotRepo(),
        diagnoses=DiagnosisRepo(),
        ai_decisions=decisions,
        feature_packages=features,
        prescriptions=prescriptions,
        traces=TraceRepo(),
        ai_client=AIClient(),
        events=events,
        audits=audits,
    )
    command = GeneratePrescriptionCommand(
        household_id=HOUSEHOLD_ID,
        diagnosis_id=DIAGNOSIS_ID,
        pgor_snapshot_id=SNAPSHOT_ID,
        actor_id=ACTOR_ID,
        request_id="req-1",
        correlation_id="corr-1",
    )

    prepared = await handler.prepare(command)
    result = await handler.infer(prepared=prepared, correlation_id="corr-1")
    prescription, decision = await handler.persist(
        command=command,
        prepared=prepared,
        result=result,
    )

    assert prepared.feature_package.provider_payload()["prescription.intensity_score"] == "0.54"
    assert prescription.status.value == "UNDER_REVIEW"
    assert decision.decision_type is AIDecisionType.PRESCRIPTION
    assert decision.structured_output["items"][0]["target_variable"] == "O"


@pytest.mark.asyncio
async def test_prescription_generation_rejects_non_bottleneck_target() -> None:
    handler = GeneratePrescriptionHandler(
        snapshots=SnapshotRepo(),
        diagnoses=DiagnosisRepo(),
        ai_decisions=AIDecisionRepo(),
        feature_packages=FeatureRepo(),
        prescriptions=PrescriptionRepo(),
        traces=TraceRepo(),
        ai_client=AIClient(bad_target=True),
        events=Recorder(),
        audits=Recorder(),
    )
    command = GeneratePrescriptionCommand(
        household_id=HOUSEHOLD_ID,
        diagnosis_id=DIAGNOSIS_ID,
        pgor_snapshot_id=SNAPSHOT_ID,
        actor_id=ACTOR_ID,
        request_id="req-2",
        correlation_id="corr-2",
    )
    prepared = await handler.prepare(command)

    with pytest.raises(
        PrescriptionGenerationError,
        match="PRESCRIPTION_TARGET_NOT_BOTTLENECK",
    ):
        await handler.infer(prepared=prepared, correlation_id="corr-2")
