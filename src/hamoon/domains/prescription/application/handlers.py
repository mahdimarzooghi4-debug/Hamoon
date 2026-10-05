from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from hamoon.domains.family_data.ports.repositories import AcceptedStateRepository
from hamoon.domains.intelligence.domain.decisions import (
    AIDecision,
    AIDecisionStatus,
    AIDecisionType,
    AIExecutionResult,
    DecisionTrace,
    DiagnosisStatus,
)
from hamoon.domains.intelligence.domain.entities import (
    FeaturePackage,
    FeaturePackageType,
    FeatureValue,
)
from hamoon.domains.intelligence.ports.repositories import (
    AIDecisionRepository,
    DecisionTraceRepository,
    DiagnosisRepository,
    FeaturePackageRepository,
)
from hamoon.domains.pgor.domain.engine import PGORSnapshotStatus
from hamoon.domains.pgor.domain.snapshots import PGORSnapshot
from hamoon.domains.pgor.ports.repositories import PGORSnapshotRepository
from hamoon.domains.prescription.application.commands import (
    GeneratePrescriptionCommand,
)
from hamoon.domains.prescription.domain.entities import (
    Prescription,
    PrescriptionStatus,
)
from hamoon.domains.prescription.domain.errors import PrescriptionGenerationError
from hamoon.domains.prescription.domain.policy import validate_prescription_output
from hamoon.domains.prescription.ports.ai import PrescriptionAIClient
from hamoon.domains.prescription.ports.repositories import PrescriptionRepository
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder

PRESCRIPTION_FEATURE_SCHEMA_VERSION = "prescription-input-v1"

@dataclass(frozen=True, slots=True)
class PreparedPrescriptionGeneration:
    snapshot: PGORSnapshot
    feature_package: FeaturePackage
    diagnosis_id: UUID
    household_context_version: int | None = None


def _accepted_diagnosis_status(status: DiagnosisStatus) -> bool:
    return status in {
        DiagnosisStatus.CONFIRMED,
        DiagnosisStatus.MODIFIED,
        DiagnosisStatus.REPLACED,
    }


class GeneratePrescriptionHandler:
    def __init__(
        self,
        *,
        snapshots: PGORSnapshotRepository,
        diagnoses: DiagnosisRepository,
        ai_decisions: AIDecisionRepository,
        feature_packages: FeaturePackageRepository,
        prescriptions: PrescriptionRepository,
        traces: DecisionTraceRepository,
        ai_client: PrescriptionAIClient,
        accepted_state: AcceptedStateRepository | None = None,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._snapshots = snapshots
        self._diagnoses = diagnoses
        self._ai_decisions = ai_decisions
        self._feature_packages = feature_packages
        self._prescriptions = prescriptions
        self._traces = traces
        self._ai_client = ai_client
        self._accepted_state = accepted_state
        self._events = events
        self._audits = audits

    async def prepare(
        self,
        command: GeneratePrescriptionCommand,
    ) -> PreparedPrescriptionGeneration:
        diagnosis = await self._diagnoses.get(command.diagnosis_id)
        if diagnosis is None:
            raise PrescriptionGenerationError("DIAGNOSIS_NOT_FOUND")
        if diagnosis.household_id != command.household_id:
            raise PrescriptionGenerationError("DIAGNOSIS_HOUSEHOLD_MISMATCH")
        if (
            not _accepted_diagnosis_status(diagnosis.status)
            or diagnosis.accepted_payload is None
        ):
            raise PrescriptionGenerationError("ACCEPTED_DIAGNOSIS_REQUIRED")

        diagnosis_ai = await self._ai_decisions.get(diagnosis.ai_decision_id)
        if diagnosis_ai is None:
            raise PrescriptionGenerationError("DIAGNOSIS_AI_DECISION_NOT_FOUND")
        if diagnosis_ai.pgor_snapshot_id != command.pgor_snapshot_id:
            raise PrescriptionGenerationError("DIAGNOSIS_SNAPSHOT_MISMATCH")

        snapshot = await self._snapshots.get(command.pgor_snapshot_id)
        if snapshot is None:
            raise PrescriptionGenerationError("PGOR_SNAPSHOT_NOT_FOUND")
        if snapshot.household_id != command.household_id:
            raise PrescriptionGenerationError("PGOR_SNAPSHOT_HOUSEHOLD_MISMATCH")
        if snapshot.status is not PGORSnapshotStatus.OFFICIAL:
            raise PrescriptionGenerationError("PGOR_SNAPSHOT_NOT_OFFICIAL")

        existing = await self._feature_packages.get_by_snapshot(
            snapshot_id=snapshot.id,
            schema_version=PRESCRIPTION_FEATURE_SCHEMA_VERSION,
        )
        if existing is not None:
            household_context_version = (
                await self._accepted_state.context_version(command.household_id)
                if self._accepted_state is not None
                else None
            )
            return PreparedPrescriptionGeneration(
                snapshot=snapshot,
                feature_package=existing,
                diagnosis_id=diagnosis.id,
                household_context_version=household_context_version,
            )

        intensity = Decimal("1") - snapshot.e
        values = (
            FeatureValue("pgor.P", str(snapshot.p), (f"pgor_snapshot:{snapshot.id}",)),
            FeatureValue("pgor.G", str(snapshot.g), (f"pgor_snapshot:{snapshot.id}",)),
            FeatureValue("pgor.O", str(snapshot.o), (f"pgor_snapshot:{snapshot.id}",)),
            FeatureValue("pgor.R", str(snapshot.r), (f"pgor_snapshot:{snapshot.id}",)),
            FeatureValue("pgor.E", str(snapshot.e), (f"pgor_snapshot:{snapshot.id}",)),
            FeatureValue(
                "pgor.bottleneck_variables",
                [item.value for item in snapshot.bottleneck_variables],
                (f"pgor_snapshot:{snapshot.id}",),
            ),
            FeatureValue(
                "prescription.intensity_score",
                str(intensity),
                (f"pgor_snapshot:{snapshot.id}",),
            ),
            FeatureValue(
                "diagnosis.id",
                str(diagnosis.id),
                (f"diagnosis:{diagnosis.id}",),
            ),
            FeatureValue(
                "diagnosis.accepted_payload",
                diagnosis.accepted_payload,
                (f"diagnosis:{diagnosis.id}",),
            ),
            FeatureValue(
                "trace.formula_version_id",
                str(snapshot.formula_version_id),
                (f"pgor_snapshot:{snapshot.id}",),
            ),
            FeatureValue(
                "trace.engine_version",
                snapshot.engine_version,
                (f"pgor_snapshot:{snapshot.id}",),
            ),
            FeatureValue(
                "trace.scoring_version",
                snapshot.scoring_version,
                (f"pgor_snapshot:{snapshot.id}",),
            ),
        )
        canonical_diagnosis = json.dumps(
            diagnosis.accepted_payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        source_fingerprint = hashlib.sha256(
            (
                snapshot.input_fingerprint
                + "|"
                + str(diagnosis.id)
                + "|"
                + canonical_diagnosis
                + "|"
                + PRESCRIPTION_FEATURE_SCHEMA_VERSION
            ).encode("utf-8")
        ).hexdigest()
        now = datetime.now(UTC)
        package = FeaturePackage(
            id=uuid4(),
            household_id=command.household_id,
            assessment_id=snapshot.assessment_id,
            pgor_snapshot_id=snapshot.id,
            package_type=FeaturePackageType.PRESCRIPTION,
            schema_version=PRESCRIPTION_FEATURE_SCHEMA_VERSION,
            source_fingerprint=source_fingerprint,
            data_quality_flags=snapshot.data_quality_flags,
            values=values,
            created_at=now,
            created_by=command.actor_id,
        )
        await self._feature_packages.add(package)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="FeaturePackageBuilt",
                event_version=1,
                aggregate_type="FEATURE_PACKAGE",
                aggregate_id=package.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "feature_package_id": str(package.id),
                    "household_id": str(package.household_id),
                    "pgor_snapshot_id": str(snapshot.id),
                    "diagnosis_id": str(diagnosis.id),
                    "package_type": package.package_type.value,
                    "schema_version": package.schema_version,
                    "source_fingerprint": package.source_fingerprint,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="intelligence.feature_package.build",
                resource_type="FEATURE_PACKAGE",
                resource_id=package.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="AI_PRESCRIPTION",
                metadata={
                    "event_id": str(event_id),
                    "diagnosis_id": str(diagnosis.id),
                    "pgor_snapshot_id": str(snapshot.id),
                    "source_fingerprint": package.source_fingerprint,
                },
            )
        )
        household_context_version = (
            await self._accepted_state.context_version(command.household_id)
            if self._accepted_state is not None
            else None
        )
        return PreparedPrescriptionGeneration(
            snapshot=snapshot,
            feature_package=package,
            diagnosis_id=diagnosis.id,
            household_context_version=household_context_version,
        )

    async def infer(
        self,
        *,
        prepared: PreparedPrescriptionGeneration,
        correlation_id: str,
    ) -> AIExecutionResult:
        result = await self._ai_client.generate_prescription(
            feature_package=prepared.feature_package,
            correlation_id=correlation_id,
        )
        validate_prescription_output(
            output=result.output,
            feature_package=prepared.feature_package,
            diagnosis_id=prepared.diagnosis_id,
        )
        return result

    async def persist(
        self,
        *,
        command: GeneratePrescriptionCommand,
        prepared: PreparedPrescriptionGeneration,
        result: AIExecutionResult,
    ) -> tuple[Prescription, AIDecision]:
        if (
            prepared.household_context_version is not None
            and self._accepted_state is not None
        ):
            current_context_version = await self._accepted_state.context_version(
                command.household_id
            )
            if current_context_version != prepared.household_context_version:
                raise PrescriptionGenerationError(
                    "HOUSEHOLD_CONTEXT_VERSION_CONFLICT"
                )
        now = datetime.now(UTC)
        trace_id = uuid4()
        ai_decision = AIDecision(
            id=uuid4(),
            household_id=command.household_id,
            assessment_id=prepared.feature_package.assessment_id,
            feature_package_id=prepared.feature_package.id,
            pgor_snapshot_id=prepared.snapshot.id,
            decision_type=AIDecisionType.PRESCRIPTION,
            status=AIDecisionStatus.GENERATED,
            provider_code=result.provider_code,
            model_id=result.model_id,
            model_alias=result.model_alias,
            routing_policy_id=result.routing_policy_id,
            routing_policy_version=result.routing_policy_version,
            prompt_policy_version=result.prompt_policy_version,
            output_schema_version=result.output_schema_version,
            structured_output=result.output,
            trace_id=trace_id,
            generated_at=now,
        )
        prescription = Prescription(
            id=uuid4(),
            household_id=command.household_id,
            diagnosis_id=command.diagnosis_id,
            ai_decision_id=ai_decision.id,
            pgor_snapshot_id=prepared.snapshot.id,
            status=PrescriptionStatus.UNDER_REVIEW,
            version=1,
            accepted_payload=None,
            created_at=now,
            created_by=command.actor_id,
        )
        trace = DecisionTrace(
            id=trace_id,
            household_id=command.household_id,
            trace_type=AIDecisionType.PRESCRIPTION,
            state_fingerprint=prepared.feature_package.source_fingerprint,
            household_context_version=prepared.household_context_version,
            pgor_snapshot_id=prepared.snapshot.id,
            feature_package_id=prepared.feature_package.id,
            ai_decision_id=ai_decision.id,
            opened_at=now,
            prescription_id=prescription.id,
        )
        await self._ai_decisions.add(ai_decision)
        await self._prescriptions.add(prescription)
        await self._traces.add(trace)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="PrescriptionGenerated",
                event_version=1,
                aggregate_type="PRESCRIPTION",
                aggregate_id=prescription.id,
                aggregate_version=prescription.version,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "prescription_id": str(prescription.id),
                    "ai_decision_id": str(ai_decision.id),
                    "diagnosis_id": str(command.diagnosis_id),
                    "pgor_snapshot_id": str(prepared.snapshot.id),
                    "feature_package_id": str(prepared.feature_package.id),
                    "trace_id": str(trace.id),
                    "status": prescription.status.value,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="prescription.generate",
                resource_type="PRESCRIPTION",
                resource_id=prescription.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="AI_PRESCRIPTION",
                metadata={
                    "event_id": str(event_id),
                    "ai_decision_id": str(ai_decision.id),
                    "diagnosis_id": str(command.diagnosis_id),
                    "feature_package_id": str(prepared.feature_package.id),
                    "trace_id": str(trace.id),
                },
            )
        )
        return prescription, ai_decision
