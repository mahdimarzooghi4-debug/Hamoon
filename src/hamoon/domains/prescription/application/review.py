from datetime import UTC, datetime
from uuid import uuid4

from jsonschema import ValidationError, validate
from pydantic import JsonValue

from hamoon.domains.intelligence.domain.decisions import (
    HumanDecision,
    HumanDecisionAction,
    HumanDecisionContext,
    LearningSignal,
    LearningSignalQuality,
    LearningSignalType,
)
from hamoon.domains.intelligence.ports.repositories import (
    AIDecisionRepository,
    DecisionTraceRepository,
    FeaturePackageRepository,
    HumanDecisionRepository,
    LearningSignalRepository,
)
from hamoon.domains.prescription.application.commands import ReviewPrescriptionCommand
from hamoon.domains.prescription.domain.entities import Prescription, PrescriptionItem
from hamoon.domains.prescription.domain.errors import PrescriptionGenerationError
from hamoon.domains.prescription.domain.policy import (
    materialize_prescription_items,
    validate_prescription_output,
)
from hamoon.domains.prescription.ports.repositories import PrescriptionRepository
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder


class PrescriptionReviewError(ValueError):
    """Human prescription review payload or transition is invalid."""


class PrescriptionVersionConflictError(ValueError):
    """Prescription changed since the reviewer loaded it."""


def _signal_type(action: HumanDecisionAction) -> LearningSignalType:
    return {
        HumanDecisionAction.CONFIRM: LearningSignalType.PRESCRIPTION_CONFIRMED,
        HumanDecisionAction.MODIFY: LearningSignalType.PRESCRIPTION_MODIFIED,
        HumanDecisionAction.REPLACE: LearningSignalType.PRESCRIPTION_REPLACED,
        HumanDecisionAction.DEFER: LearningSignalType.PRESCRIPTION_DEFERRED,
    }[action]


def _event_type(action: HumanDecisionAction) -> str:
    return {
        HumanDecisionAction.CONFIRM: "PrescriptionApproved",
        HumanDecisionAction.MODIFY: "PrescriptionModified",
        HumanDecisionAction.REPLACE: "PrescriptionReplaced",
        HumanDecisionAction.DEFER: "PrescriptionDeferred",
    }[action]


class ReviewPrescriptionHandler:
    def __init__(
        self,
        *,
        prescriptions: PrescriptionRepository,
        ai_decisions: AIDecisionRepository,
        feature_packages: FeaturePackageRepository,
        human_decisions: HumanDecisionRepository,
        learning_signals: LearningSignalRepository,
        traces: DecisionTraceRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
        output_schema: dict[str, JsonValue],
    ) -> None:
        self._prescriptions = prescriptions
        self._ai_decisions = ai_decisions
        self._feature_packages = feature_packages
        self._human_decisions = human_decisions
        self._learning_signals = learning_signals
        self._traces = traces
        self._events = events
        self._audits = audits
        self._output_schema = output_schema

    async def handle(
        self,
        command: ReviewPrescriptionCommand,
    ) -> tuple[Prescription, HumanDecision, LearningSignal, tuple[PrescriptionItem, ...]]:
        prescription = await self._prescriptions.get(command.prescription_id)
        if prescription is None:
            raise PrescriptionReviewError("PRESCRIPTION_NOT_FOUND")
        if prescription.version != command.expected_version:
            raise PrescriptionVersionConflictError("Prescription version changed.")
        if command.action not in {
            HumanDecisionAction.CONFIRM,
            HumanDecisionAction.MODIFY,
            HumanDecisionAction.REPLACE,
            HumanDecisionAction.DEFER,
        }:
            raise PrescriptionReviewError("PRESCRIPTION_REVIEW_ACTION_INVALID")

        ai_decision = await self._ai_decisions.get(prescription.ai_decision_id)
        if ai_decision is None:
            raise PrescriptionReviewError("PRESCRIPTION_AI_DECISION_NOT_FOUND")
        package = await self._feature_packages.get(ai_decision.feature_package_id)
        if package is None:
            raise PrescriptionReviewError("FEATURE_PACKAGE_NOT_FOUND")

        if command.action is HumanDecisionAction.CONFIRM:
            payload = ai_decision.structured_output
        elif command.action in {
            HumanDecisionAction.MODIFY,
            HumanDecisionAction.REPLACE,
        }:
            if not command.reason_code and not command.reason_text:
                raise PrescriptionReviewError("PRESCRIPTION_CHANGE_REASON_REQUIRED")
            if command.modified_payload is None:
                raise PrescriptionReviewError("MODIFIED_PAYLOAD_REQUIRED")
            payload = command.modified_payload
        else:
            payload = None

        accepted_items: tuple[PrescriptionItem, ...] = ()
        if payload is not None:
            try:
                validate(instance=payload, schema=self._output_schema)
                validate_prescription_output(
                    output=payload,
                    feature_package=package,
                    diagnosis_id=prescription.diagnosis_id,
                )
            except ValidationError as exc:
                raise PrescriptionReviewError(
                    "HUMAN_PRESCRIPTION_SCHEMA_INVALID"
                ) from exc
            except PrescriptionGenerationError as exc:
                raise PrescriptionReviewError(str(exc)) from exc

            accepted_items = materialize_prescription_items(
                prescription_id=prescription.id,
                output=payload,
                machine_proposed=command.action is HumanDecisionAction.CONFIRM,
                id_factory=uuid4,
            )

        now = datetime.now(UTC)
        human_decision_id = uuid4()
        try:
            updated = prescription.review(
                action=command.action,
                accepted_payload=payload,
                human_decision_id=human_decision_id,
                actor_id=command.actor_id,
                decided_at=now,
            )
        except ValueError as exc:
            raise PrescriptionReviewError(str(exc)) from exc

        human_decision = HumanDecision(
            id=human_decision_id,
            household_id=prescription.household_id,
            ai_decision_id=prescription.ai_decision_id,
            actor_id=command.actor_id,
            action=command.action,
            reason_code=command.reason_code,
            reason_text=command.reason_text,
            accepted_payload=payload,
            modified_payload=command.modified_payload,
            decided_at=now,
            decision_context=HumanDecisionContext.PRESCRIPTION,
            prescription_id=prescription.id,
        )
        signal = LearningSignal(
            id=uuid4(),
            household_id=prescription.household_id,
            signal_type=_signal_type(command.action),
            ai_decision_id=prescription.ai_decision_id,
            human_decision_id=human_decision.id,
            diagnosis_id=prescription.diagnosis_id,
            signal_label=command.action.value,
            quality_status=LearningSignalQuality.RAW,
            created_at=now,
            created_by=command.actor_id,
            prescription_id=prescription.id,
        )

        await self._human_decisions.add(human_decision)
        await self._prescriptions.update(
            updated,
            expected_version=command.expected_version,
        )
        if accepted_items:
            await self._prescriptions.add_items(accepted_items)
        await self._learning_signals.add(signal)
        await self._traces.attach_human_decision(
            ai_decision_id=prescription.ai_decision_id,
            human_decision_id=human_decision.id,
            closed_at=(
                None
                if command.action is HumanDecisionAction.DEFER
                else now
            ),
        )

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type=_event_type(command.action),
                event_version=1,
                aggregate_type="PRESCRIPTION",
                aggregate_id=prescription.id,
                aggregate_version=updated.version,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "prescription_id": str(prescription.id),
                    "diagnosis_id": str(prescription.diagnosis_id),
                    "ai_decision_id": str(prescription.ai_decision_id),
                    "human_decision_id": str(human_decision.id),
                    "learning_signal_id": str(signal.id),
                    "accepted_item_ids": [str(item.id) for item in accepted_items],
                    "status": updated.status.value,
                    "version": updated.version,
                },
            )
        )
        await self._events.record(
            DomainEventRecord(
                event_id=uuid4(),
                event_type="LearningSignalCreated",
                event_version=1,
                aggregate_type="LEARNING_SIGNAL",
                aggregate_id=signal.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=event_id,
                payload={
                    "learning_signal_id": str(signal.id),
                    "household_id": str(signal.household_id),
                    "signal_type": signal.signal_type.value,
                    "ai_decision_id": str(signal.ai_decision_id),
                    "human_decision_id": str(signal.human_decision_id),
                    "prescription_id": str(prescription.id),
                    "quality_status": signal.quality_status.value,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="prescription.review",
                resource_type="PRESCRIPTION",
                resource_id=prescription.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="HUMAN_REVIEW",
                metadata={
                    "event_id": str(event_id),
                    "human_decision_id": str(human_decision.id),
                    "learning_signal_id": str(signal.id),
                    "review_action": command.action.value,
                    "accepted_item_count": len(accepted_items),
                    "version": updated.version,
                },
            )
        )
        return updated, human_decision, signal, accepted_items
