from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from hamoon.domains.assessment.application.commands import (
    ChangeObservationValidationCommand,
    RecordIndicatorObservationCommand,
    ResolveAcceptedObservationCommand,
    StartAssessmentCommand,
)
from hamoon.domains.assessment.domain.entities import (
    AcceptedIndicatorObservation,
    Assessment,
    AssessmentReadiness,
    AssessmentReadinessStatus,
    AssessmentStatus,
    IndicatorObservation,
    ObservationValidationState,
    ObservationValidationStatus,
)
from hamoon.domains.assessment.domain.errors import (
    AcceptedObservationVersionConflictError,
    AssessmentNotFoundError,
    DefinitionNotAvailableError,
    IndicatorNotInDefinitionError,
    ObservationNotFoundError,
    ObservationNotValidatedError,
    ValidationVersionConflictError,
)
from hamoon.domains.assessment.ports.repositories import (
    AcceptedObservationRepository,
    AssessmentRepository,
    IndicatorObservationRepository,
    ObservationValidationRepository,
)
from hamoon.domains.family_data.ports.repositories import DataSourceRepository
from hamoon.domains.pgor.domain.definitions import (
    PGORDefinitionStatus,
    RequirementPolicyStatus,
)
from hamoon.domains.pgor.ports.repositories import PGORDefinitionRepository
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder


class StartAssessmentHandler:
    def __init__(
        self,
        *,
        assessments: AssessmentRepository,
        definitions: PGORDefinitionRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._assessments = assessments
        self._definitions = definitions
        self._events = events
        self._audits = audits

    async def handle(self, command: StartAssessmentCommand) -> Assessment:
        definition = await self._definitions.get_version(command.definition_version_id)
        if definition is None or definition.status not in {
            PGORDefinitionStatus.APPROVED,
            PGORDefinitionStatus.ACTIVE,
        }:
            raise DefinitionNotAvailableError(str(command.definition_version_id))

        now = datetime.now(UTC)
        assessment = Assessment(
            id=uuid4(),
            household_id=command.household_id,
            assessment_type=command.assessment_type,
            definition_version_id=command.definition_version_id,
            status=AssessmentStatus.IN_PROGRESS,
            version=1,
            started_at=now,
            started_by=command.actor_id,
            reason=command.reason,
        )
        await self._assessments.add(assessment)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="AssessmentStarted",
                event_version=1,
                aggregate_type="ASSESSMENT",
                aggregate_id=assessment.id,
                aggregate_version=assessment.version,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "assessment_id": str(assessment.id),
                    "household_id": str(assessment.household_id),
                    "assessment_type": assessment.assessment_type.value,
                    "definition_version_id": str(assessment.definition_version_id),
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="assessment.create",
                resource_type="ASSESSMENT",
                resource_id=assessment.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="EMPOWERMENT_ASSESSMENT",
                metadata={"event_id": str(event_id)},
            )
        )
        return assessment


class RecordIndicatorObservationHandler:
    def __init__(
        self,
        *,
        assessments: AssessmentRepository,
        definitions: PGORDefinitionRepository,
        sources: DataSourceRepository,
        observations: IndicatorObservationRepository,
        validations: ObservationValidationRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._assessments = assessments
        self._definitions = definitions
        self._sources = sources
        self._observations = observations
        self._validations = validations
        self._events = events
        self._audits = audits

    async def handle(
        self,
        command: RecordIndicatorObservationCommand,
    ) -> tuple[IndicatorObservation, ObservationValidationState]:
        assessment = await self._assessments.get(command.assessment_id)
        if assessment is None:
            raise AssessmentNotFoundError(str(command.assessment_id))

        indicator = await self._definitions.get_indicator(
            definition_version_id=assessment.definition_version_id,
            indicator_id=command.indicator_definition_id,
        )
        if indicator is None:
            raise IndicatorNotInDefinitionError(str(command.indicator_definition_id))

        source = await self._sources.get(command.source_id)
        if source is None or not source.active:
            raise DefinitionNotAvailableError("Data source unavailable.")

        now = datetime.now(UTC)
        observation = IndicatorObservation(
            id=uuid4(),
            assessment_id=assessment.id,
            indicator_definition_id=indicator.id,
            raw_score_0_100=command.raw_score_0_100,
            source_id=source.id,
            source_detail=command.source_detail,
            effective_at=command.effective_at,
            observed_at=now,
            observed_by=command.actor_id,
            version=1,
        )
        validation = ObservationValidationState(
            observation_id=observation.id,
            status=ObservationValidationStatus.PENDING_VALIDATION,
            version=1,
            changed_at=now,
            changed_by=command.actor_id,
            reason_code="OBSERVATION_RECORDED",
        )

        await self._observations.add(observation)
        await self._validations.create_initial(validation)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="IndicatorObservationRecorded",
                event_version=1,
                aggregate_type="ASSESSMENT",
                aggregate_id=assessment.id,
                aggregate_version=assessment.version,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "assessment_id": str(assessment.id),
                    "observation_id": str(observation.id),
                    "indicator_definition_id": str(indicator.id),
                    "raw_score_0_100": str(observation.raw_score_0_100),
                    "source_id": str(source.id),
                    "source_type": source.source_type.value,
                    "validation_status": validation.status.value,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="assessment.observation.create",
                resource_type="ASSESSMENT",
                resource_id=assessment.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="EMPOWERMENT_ASSESSMENT",
                metadata={
                    "event_id": str(event_id),
                    "observation_id": str(observation.id),
                    "indicator_definition_id": str(indicator.id),
                    "validation_status": validation.status.value,
                },
            )
        )
        return observation, validation


class ChangeObservationValidationHandler:
    def __init__(
        self,
        *,
        observations: IndicatorObservationRepository,
        validations: ObservationValidationRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._observations = observations
        self._validations = validations
        self._events = events
        self._audits = audits

    async def handle(
        self,
        command: ChangeObservationValidationCommand,
    ) -> ObservationValidationState:
        observation = await self._observations.get_for_assessment(
            assessment_id=command.assessment_id,
            observation_id=command.observation_id,
        )
        if observation is None:
            raise ObservationNotFoundError(str(command.observation_id))

        previous = await self._validations.get_state(observation.id)
        if previous is None:
            raise RuntimeError("Observation validation state is missing.")
        if previous.version != command.expected_validation_version:
            raise ValidationVersionConflictError("Observation validation version changed.")

        now = datetime.now(UTC)
        current = previous.transition(
            to_status=command.to_status,
            changed_at=now,
            changed_by=command.actor_id,
            reason_code=command.reason_code,
            reason_text=command.reason_text,
        )
        await self._validations.transition(previous=previous, current=current)

        event_type = {
            ObservationValidationStatus.VALIDATED: "IndicatorObservationValidated",
            ObservationValidationStatus.DISPUTED: "IndicatorObservationDisputed",
            ObservationValidationStatus.REJECTED: "IndicatorObservationRejected",
            ObservationValidationStatus.SUPERSEDED: "IndicatorObservationSuperseded",
            ObservationValidationStatus.PENDING_VALIDATION: "IndicatorObservationValidationPending",
        }[current.status]
        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type=event_type,
                event_version=1,
                aggregate_type="ASSESSMENT",
                aggregate_id=command.assessment_id,
                aggregate_version=current.version,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "assessment_id": str(command.assessment_id),
                    "observation_id": str(observation.id),
                    "indicator_definition_id": str(observation.indicator_definition_id),
                    "from_status": previous.status.value,
                    "to_status": current.status.value,
                    "validation_version": current.version,
                    "reason_code": command.reason_code,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="assessment.observation.validation.change",
                resource_type="ASSESSMENT",
                resource_id=command.assessment_id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="DATA_VALIDATION",
                metadata={
                    "event_id": str(event_id),
                    "observation_id": str(observation.id),
                    "from_status": previous.status.value,
                    "to_status": current.status.value,
                },
            )
        )
        return current


class ResolveAcceptedObservationHandler:
    def __init__(
        self,
        *,
        observations: IndicatorObservationRepository,
        validations: ObservationValidationRepository,
        accepted_observations: AcceptedObservationRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._observations = observations
        self._validations = validations
        self._accepted_observations = accepted_observations
        self._events = events
        self._audits = audits

    async def handle(
        self,
        command: ResolveAcceptedObservationCommand,
    ) -> AcceptedIndicatorObservation:
        observation = await self._observations.get_for_assessment(
            assessment_id=command.assessment_id,
            observation_id=command.observation_id,
        )
        if observation is None:
            raise ObservationNotFoundError(str(command.observation_id))
        if observation.indicator_definition_id != command.indicator_definition_id:
            raise IndicatorNotInDefinitionError(str(command.indicator_definition_id))

        validation = await self._validations.get_state(observation.id)
        if (
            validation is None
            or validation.status is not ObservationValidationStatus.VALIDATED
        ):
            raise ObservationNotValidatedError(str(observation.id))

        previous = await self._accepted_observations.get(
            assessment_id=command.assessment_id,
            indicator_definition_id=command.indicator_definition_id,
        )
        actual_version = 0 if previous is None else previous.projection_version
        if actual_version != command.expected_projection_version:
            raise AcceptedObservationVersionConflictError(
                "Accepted-observation projection changed."
            )

        now = datetime.now(UTC)
        accepted = AcceptedIndicatorObservation(
            assessment_id=command.assessment_id,
            indicator_definition_id=command.indicator_definition_id,
            observation_id=observation.id,
            projection_version=actual_version + 1,
            changed_at=now,
            changed_by=command.actor_id,
        )
        event_id = uuid4()

        await self._accepted_observations.set_current(
            accepted=accepted,
            previous_observation_id=(
                None if previous is None else previous.observation_id
            ),
            reason_code=command.reason_code,
            reason_text=command.reason_text,
            event_id=event_id,
        )
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="AssessmentAcceptedObservationChanged",
                event_version=1,
                aggregate_type="ASSESSMENT",
                aggregate_id=command.assessment_id,
                aggregate_version=accepted.projection_version,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "assessment_id": str(command.assessment_id),
                    "indicator_definition_id": str(command.indicator_definition_id),
                    "previous_observation_id": (
                        None if previous is None else str(previous.observation_id)
                    ),
                    "new_observation_id": str(observation.id),
                    "projection_version": accepted.projection_version,
                    "reason_code": command.reason_code,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="assessment.accepted_observation.resolve",
                resource_type="ASSESSMENT",
                resource_id=command.assessment_id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="DATA_VALIDATION",
                metadata={
                    "event_id": str(event_id),
                    "indicator_definition_id": str(command.indicator_definition_id),
                    "observation_id": str(observation.id),
                    "projection_version": accepted.projection_version,
                },
            )
        )
        return accepted


class EvaluateAssessmentReadinessHandler:
    def __init__(
        self,
        *,
        assessments: AssessmentRepository,
        definitions: PGORDefinitionRepository,
        accepted_observations: AcceptedObservationRepository,
        validations: ObservationValidationRepository,
    ) -> None:
        self._assessments = assessments
        self._definitions = definitions
        self._accepted_observations = accepted_observations
        self._validations = validations

    async def handle(self, assessment_id: UUID) -> AssessmentReadiness:
        assessment = await self._assessments.get(assessment_id)
        if assessment is None:
            raise AssessmentNotFoundError(str(assessment_id))

        definition = await self._definitions.get_version(
            assessment.definition_version_id
        )
        if definition is None:
            raise DefinitionNotAvailableError(str(assessment.definition_version_id))

        indicators = await self._definitions.list_indicators(
            assessment.definition_version_id
        )
        accepted = await self._accepted_observations.list_for_assessment(assessment.id)
        unresolved_count = await self._validations.count_unresolved_for_assessment(
            assessment.id
        )

        accepted_by_indicator = {
            item.indicator_definition_id: item for item in accepted
        }
        total_count = len(indicators)
        accepted_count = len(accepted_by_indicator)
        accepted_observation_ids = tuple(
            sorted(
                (item.observation_id for item in accepted),
                key=str,
            )
        )

        if definition.requirement_policy_status is RequirementPolicyStatus.UNRESOLVED:
            return AssessmentReadiness(
                assessment_id=assessment.id,
                status=AssessmentReadinessStatus.REQUIREMENT_POLICY_UNRESOLVED,
                total_indicator_count=total_count,
                accepted_indicator_count=accepted_count,
                required_indicator_count=None,
                accepted_required_indicator_count=None,
                completeness_ratio=None,
                missing_required_indicator_ids=(),
                unresolved_validation_count=unresolved_count,
                blocking_reasons=("REQUIREMENT_POLICY_UNRESOLVED",),
                accepted_observation_ids=accepted_observation_ids,
            )

        unresolved_requirement_flags = [
            indicator.id
            for indicator in indicators
            if indicator.required_for_complete_assessment is None
        ]
        if unresolved_requirement_flags:
            return AssessmentReadiness(
                assessment_id=assessment.id,
                status=AssessmentReadinessStatus.REQUIREMENT_POLICY_UNRESOLVED,
                total_indicator_count=total_count,
                accepted_indicator_count=accepted_count,
                required_indicator_count=None,
                accepted_required_indicator_count=None,
                completeness_ratio=None,
                missing_required_indicator_ids=(),
                unresolved_validation_count=unresolved_count,
                blocking_reasons=("REQUIREMENT_POLICY_INCOMPLETE",),
                accepted_observation_ids=accepted_observation_ids,
            )

        required = [
            indicator
            for indicator in indicators
            if indicator.required_for_complete_assessment is True
        ]
        missing = tuple(
            indicator.id
            for indicator in required
            if indicator.id not in accepted_by_indicator
        )
        required_count = len(required)
        accepted_required_count = required_count - len(missing)
        completeness = (
            Decimal("1")
            if required_count == 0
            else Decimal(accepted_required_count) / Decimal(required_count)
        )

        blocking: list[str] = []
        if missing:
            blocking.append("MISSING_REQUIRED_INDICATOR")

        status = (
            AssessmentReadinessStatus.READY
            if not blocking
            else AssessmentReadinessStatus.INCOMPLETE
        )

        return AssessmentReadiness(
            assessment_id=assessment.id,
            status=status,
            total_indicator_count=total_count,
            accepted_indicator_count=accepted_count,
            required_indicator_count=required_count,
            accepted_required_indicator_count=accepted_required_count,
            completeness_ratio=completeness,
            missing_required_indicator_ids=missing,
            unresolved_validation_count=unresolved_count,
            blocking_reasons=tuple(blocking),
            accepted_observation_ids=accepted_observation_ids,
        )
