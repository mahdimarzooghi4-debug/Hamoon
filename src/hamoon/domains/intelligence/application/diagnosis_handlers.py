from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from jsonschema import ValidationError, validate
from pydantic import JsonValue

from hamoon.domains.intelligence.application.commands import (
    BuildDiagnosisFeaturePackageCommand,
)
from hamoon.domains.intelligence.application.diagnosis_commands import (
    GenerateDiagnosisCommand,
    ReviewDiagnosisCommand,
)
from hamoon.domains.intelligence.application.handlers import (
    BuildDiagnosisFeaturePackageHandler,
)
from hamoon.domains.intelligence.domain.decisions import (
    AIDecision,
    AIExecutionResult,
    AIDecisionStatus,
    AIDecisionType,
    DecisionTrace,
    Diagnosis,
    DiagnosisStatus,
    HumanDecision,
    HumanDecisionAction,
    HumanDecisionContext,
    LearningSignal,
    LearningSignalQuality,
    LearningSignalType,
)
from hamoon.domains.intelligence.domain.errors import (
    AIDecisionNotFoundError,
    DiagnosisGenerationError,
    DiagnosisNotFoundError,
    DiagnosisVersionConflictError,
    InvalidDiagnosisReviewError,
)
from hamoon.domains.intelligence.domain.entities import FeaturePackage
from hamoon.domains.intelligence.ports.ai import DiagnosisAIClient
from hamoon.domains.intelligence.ports.repositories import (
    AIDecisionRepository,
    DecisionTraceRepository,
    DiagnosisRepository,
    FeaturePackageRepository,
    HumanDecisionRepository,
    LearningSignalRepository,
)
from hamoon.domains.pgor.domain.engine import PGORSnapshotStatus
from hamoon.domains.pgor.domain.snapshots import PGORSnapshot
from hamoon.domains.pgor.ports.repositories import (
    PGORDefinitionRepository,
    PGORSnapshotRepository,
)
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder


def _validate_grounding(
    *,
    output: dict[str, JsonValue],
    available_feature_keys: set[str],
) -> None:
    items = output.get("items")
    if not isinstance(items, list):
        raise DiagnosisGenerationError("AI_OUTPUT_ITEMS_INVALID")

    for item in items:
        if not isinstance(item, dict):
            raise DiagnosisGenerationError("AI_OUTPUT_ITEM_INVALID")
        refs = item.get("supporting_feature_refs")
        if not isinstance(refs, list):
            raise DiagnosisGenerationError("AI_OUTPUT_GROUNDING_FAILED")
        for ref in refs:
            if not isinstance(ref, str) or ref not in available_feature_keys:
                raise DiagnosisGenerationError("AI_OUTPUT_GROUNDING_FAILED")


@dataclass(frozen=True, slots=True)
class PreparedDiagnosisGeneration:
    snapshot: PGORSnapshot
    feature_package: FeaturePackage


def _learning_signal_type(action: HumanDecisionAction) -> LearningSignalType:
    return {
        HumanDecisionAction.CONFIRM: LearningSignalType.DIAGNOSIS_CONFIRMED,
        HumanDecisionAction.MODIFY: LearningSignalType.DIAGNOSIS_MODIFIED,
        HumanDecisionAction.REPLACE: LearningSignalType.DIAGNOSIS_REPLACED,
        HumanDecisionAction.REJECT: LearningSignalType.DIAGNOSIS_REJECTED,
        HumanDecisionAction.DEFER: LearningSignalType.DIAGNOSIS_DEFERRED,
    }[action]


class GenerateDiagnosisHandler:
    def __init__(
        self,
        *,
        snapshots: PGORSnapshotRepository,
        definitions: PGORDefinitionRepository,
        feature_packages: FeaturePackageRepository,
        ai_decisions: AIDecisionRepository,
        diagnoses: DiagnosisRepository,
        traces: DecisionTraceRepository,
        ai_client: DiagnosisAIClient,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._snapshots = snapshots
        self._definitions = definitions
        self._feature_packages = feature_packages
        self._ai_decisions = ai_decisions
        self._diagnoses = diagnoses
        self._traces = traces
        self._ai_client = ai_client
        self._events = events
        self._audits = audits

    async def prepare(
        self,
        command: GenerateDiagnosisCommand,
    ) -> PreparedDiagnosisGeneration:
        snapshot = await self._snapshots.get(command.pgor_snapshot_id)
        if snapshot is None:
            raise DiagnosisGenerationError("PGOR_SNAPSHOT_NOT_FOUND")
        if snapshot.household_id != command.household_id:
            raise DiagnosisGenerationError("PGOR_SNAPSHOT_HOUSEHOLD_MISMATCH")
        if snapshot.status is not PGORSnapshotStatus.OFFICIAL:
            raise DiagnosisGenerationError("PGOR_SNAPSHOT_NOT_OFFICIAL")

        package = await BuildDiagnosisFeaturePackageHandler(
            snapshots=self._snapshots,
            definitions=self._definitions,
            packages=self._feature_packages,
            events=self._events,
            audits=self._audits,
        ).handle(
            BuildDiagnosisFeaturePackageCommand(
                snapshot_id=snapshot.id,
                actor_id=command.actor_id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
            )
        )
        return PreparedDiagnosisGeneration(
            snapshot=snapshot,
            feature_package=package,
        )

    async def infer(
        self,
        *,
        prepared: PreparedDiagnosisGeneration,
        correlation_id: str,
    ) -> AIExecutionResult:
        result = await self._ai_client.generate_diagnosis(
            feature_package=prepared.feature_package,
            correlation_id=correlation_id,
        )
        _validate_grounding(
            output=result.output,
            available_feature_keys=set(
                prepared.feature_package.provider_payload().keys()
            ),
        )
        return result

    async def persist(
        self,
        *,
        command: GenerateDiagnosisCommand,
        prepared: PreparedDiagnosisGeneration,
        result: AIExecutionResult,
    ) -> tuple[Diagnosis, AIDecision]:
        snapshot = prepared.snapshot
        package = prepared.feature_package
        now = datetime.now(UTC)
        trace_id = uuid4()
        ai_decision = AIDecision(
            id=uuid4(),
            household_id=command.household_id,
            assessment_id=package.assessment_id,
            feature_package_id=package.id,
            pgor_snapshot_id=snapshot.id,
            decision_type=AIDecisionType.DIAGNOSIS,
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
        diagnosis = Diagnosis(
            id=uuid4(),
            household_id=command.household_id,
            ai_decision_id=ai_decision.id,
            status=DiagnosisStatus.UNDER_REVIEW,
            version=1,
            accepted_payload=None,
            created_at=now,
        )
        trace = DecisionTrace(
            id=trace_id,
            household_id=command.household_id,
            trace_type=AIDecisionType.DIAGNOSIS,
            state_fingerprint=package.source_fingerprint,
            pgor_snapshot_id=snapshot.id,
            feature_package_id=package.id,
            ai_decision_id=ai_decision.id,
            opened_at=now,
        )

        await self._ai_decisions.add(ai_decision)
        await self._diagnoses.add(diagnosis)
        await self._traces.add(trace)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="DiagnosisGenerated",
                event_version=1,
                aggregate_type="DIAGNOSIS",
                aggregate_id=diagnosis.id,
                aggregate_version=diagnosis.version,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "diagnosis_id": str(diagnosis.id),
                    "ai_decision_id": str(ai_decision.id),
                    "household_id": str(command.household_id),
                    "pgor_snapshot_id": str(snapshot.id),
                    "feature_package_id": str(package.id),
                    "trace_id": str(trace.id),
                    "model_alias": ai_decision.model_alias,
                    "routing_policy_version": ai_decision.routing_policy_version,
                    "prompt_policy_version": ai_decision.prompt_policy_version,
                    "output_schema_version": ai_decision.output_schema_version,
                    "status": diagnosis.status.value,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="diagnosis.generate",
                resource_type="DIAGNOSIS",
                resource_id=diagnosis.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="AI_DIAGNOSIS",
                metadata={
                    "event_id": str(event_id),
                    "ai_decision_id": str(ai_decision.id),
                    "trace_id": str(trace.id),
                    "feature_package_id": str(package.id),
                    "model_alias": ai_decision.model_alias,
                },
            )
        )
        return diagnosis, ai_decision

    async def handle(
        self,
        command: GenerateDiagnosisCommand,
    ) -> tuple[Diagnosis, AIDecision]:
        prepared = await self.prepare(command)
        result = await self.infer(
            prepared=prepared,
            correlation_id=command.correlation_id,
        )
        return await self.persist(
            command=command,
            prepared=prepared,
            result=result,
        )


class ReviewDiagnosisHandler:
    def __init__(
        self,
        *,
        diagnoses: DiagnosisRepository,
        ai_decisions: AIDecisionRepository,
        human_decisions: HumanDecisionRepository,
        feature_packages: FeaturePackageRepository,
        traces: DecisionTraceRepository,
        learning_signals: LearningSignalRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
        output_schema: dict[str, JsonValue],
    ) -> None:
        self._diagnoses = diagnoses
        self._ai_decisions = ai_decisions
        self._human_decisions = human_decisions
        self._feature_packages = feature_packages
        self._traces = traces
        self._learning_signals = learning_signals
        self._events = events
        self._audits = audits
        self._output_schema = output_schema

    async def handle(
        self,
        command: ReviewDiagnosisCommand,
    ) -> tuple[Diagnosis, HumanDecision, LearningSignal]:
        diagnosis = await self._diagnoses.get(command.diagnosis_id)
        if diagnosis is None:
            raise DiagnosisNotFoundError(str(command.diagnosis_id))
        if diagnosis.version != command.expected_version:
            raise DiagnosisVersionConflictError("Diagnosis version changed.")

        ai_decision = await self._ai_decisions.get(diagnosis.ai_decision_id)
        if ai_decision is None:
            raise AIDecisionNotFoundError(str(diagnosis.ai_decision_id))

        payload: dict[str, JsonValue] | None
        if command.action is HumanDecisionAction.CONFIRM:
            payload = ai_decision.structured_output
        elif command.action in {
            HumanDecisionAction.MODIFY,
            HumanDecisionAction.REPLACE,
        }:
            if command.modified_payload is None:
                raise InvalidDiagnosisReviewError("MODIFIED_PAYLOAD_REQUIRED")
            try:
                validate(instance=command.modified_payload, schema=self._output_schema)
            except ValidationError as exc:
                raise InvalidDiagnosisReviewError(
                    "HUMAN_DIAGNOSIS_SCHEMA_INVALID"
                ) from exc
            package = await self._feature_packages.get(ai_decision.feature_package_id)
            if package is None:
                raise InvalidDiagnosisReviewError("FEATURE_PACKAGE_NOT_FOUND")
            try:
                _validate_grounding(
                    output=command.modified_payload,
                    available_feature_keys=set(package.provider_payload().keys()),
                )
            except DiagnosisGenerationError as exc:
                raise InvalidDiagnosisReviewError(str(exc)) from exc
            payload = command.modified_payload
        else:
            payload = None

        now = datetime.now(UTC)
        human_decision_id = uuid4()
        try:
            updated = diagnosis.review(
                action=command.action,
                accepted_payload=payload,
                human_decision_id=human_decision_id,
                actor_id=command.actor_id,
                decided_at=now,
            )
        except ValueError as exc:
            raise InvalidDiagnosisReviewError(str(exc)) from exc

        human_decision = HumanDecision(
            id=human_decision_id,
            household_id=diagnosis.household_id,
            ai_decision_id=diagnosis.ai_decision_id,
            actor_id=command.actor_id,
            action=command.action,
            reason_code=command.reason_code,
            reason_text=command.reason_text,
            accepted_payload=payload,
            modified_payload=command.modified_payload,
            decided_at=now,
            decision_context=HumanDecisionContext.DIAGNOSIS,
            diagnosis_id=diagnosis.id,
        )
        signal = LearningSignal(
            id=uuid4(),
            household_id=diagnosis.household_id,
            signal_type=_learning_signal_type(command.action),
            ai_decision_id=diagnosis.ai_decision_id,
            human_decision_id=human_decision.id,
            diagnosis_id=diagnosis.id,
            signal_label=command.action.value,
            quality_status=LearningSignalQuality.RAW,
            created_at=now,
            created_by=command.actor_id,
        )

        await self._human_decisions.add(human_decision)
        await self._diagnoses.update(
            updated,
            expected_version=command.expected_version,
        )
        await self._learning_signals.add(signal)
        await self._traces.attach_human_decision(
            ai_decision_id=diagnosis.ai_decision_id,
            human_decision_id=human_decision.id,
            learning_signal_id=signal.id,
            closed_at=(
                None
                if command.action is HumanDecisionAction.DEFER
                else now
            ),
        )

        event_type = {
            HumanDecisionAction.CONFIRM: "DiagnosisConfirmed",
            HumanDecisionAction.MODIFY: "DiagnosisModified",
            HumanDecisionAction.REPLACE: "DiagnosisReplaced",
            HumanDecisionAction.REJECT: "DiagnosisRejected",
            HumanDecisionAction.DEFER: "DiagnosisDeferred",
        }[command.action]
        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type=event_type,
                event_version=1,
                aggregate_type="DIAGNOSIS",
                aggregate_id=diagnosis.id,
                aggregate_version=updated.version,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "diagnosis_id": str(diagnosis.id),
                    "ai_decision_id": str(diagnosis.ai_decision_id),
                    "human_decision_id": str(human_decision.id),
                    "learning_signal_id": str(signal.id),
                    "action": command.action.value,
                    "status": updated.status.value,
                    "version": updated.version,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="diagnosis.review",
                resource_type="DIAGNOSIS",
                resource_id=diagnosis.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="HUMAN_REVIEW",
                metadata={
                    "event_id": str(event_id),
                    "ai_decision_id": str(diagnosis.ai_decision_id),
                    "human_decision_id": str(human_decision.id),
                    "learning_signal_id": str(signal.id),
                    "review_action": command.action.value,
                    "version": updated.version,
                },
            )
        )
        return updated, human_decision, signal
