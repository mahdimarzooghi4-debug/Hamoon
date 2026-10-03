from datetime import UTC, datetime
from uuid import uuid4

from hamoon.domains.family_data.application.commands import (
    ChangeFactValidationCommand,
    RecordHouseholdFactCommand,
    ResolveAcceptedFactCommand,
)
from hamoon.domains.family_data.domain.entities import (
    CurrentAcceptedFact,
    FactValidationState,
    FactValidationStatus,
    HouseholdFact,
    validate_fact_value,
)
from hamoon.domains.family_data.domain.errors import (
    DataSourceNotFoundError,
    FactNotValidatedError,
    FactTypeMismatchError,
    HouseholdFactNotFoundError,
    ProjectionVersionConflictError,
)
from hamoon.domains.family_data.ports.repositories import (
    AcceptedStateRepository,
    DataSourceRepository,
    FactValidationRepository,
    HouseholdFactRepository,
)
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder


class RecordHouseholdFactHandler:
    def __init__(
        self,
        *,
        sources: DataSourceRepository,
        facts: HouseholdFactRepository,
        validations: FactValidationRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._sources = sources
        self._facts = facts
        self._validations = validations
        self._events = events
        self._audits = audits

    async def handle(self, command: RecordHouseholdFactCommand) -> HouseholdFact:
        source = await self._sources.get(command.source_id)
        if source is None or not source.active:
            raise DataSourceNotFoundError(str(command.source_id))

        validate_fact_value(command.value_type, command.value)

        now = datetime.now(UTC)
        fact = HouseholdFact(
            id=uuid4(),
            household_id=command.household_id,
            fact_type=command.fact_type,
            value_type=command.value_type,
            value=command.value,
            source_id=source.id,
            source_detail=command.source_detail,
            effective_from=command.effective_from,
            effective_to=None,
            recorded_at=now,
            recorded_by=command.actor_id,
            version=1,
            supersedes_fact_id=None,
            schema_version=1,
        )
        validation = FactValidationState(
            fact_id=fact.id,
            status=FactValidationStatus.PENDING_VALIDATION,
            version=1,
            changed_at=now,
            changed_by=command.actor_id,
            reason_code="FACT_RECORDED",
            reason_text=None,
        )

        await self._facts.add(fact)
        await self._validations.create_initial(state=validation, occurred_at=now)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="HouseholdFactRecorded",
                event_version=2,
                aggregate_type="HOUSEHOLD_FACT",
                aggregate_id=fact.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "fact_id": str(fact.id),
                    "household_id": str(fact.household_id),
                    "fact_type": fact.fact_type,
                    "value_type": fact.value_type.value,
                    "source_id": str(source.id),
                    "source_type": source.source_type.value,
                    "effective_from": fact.effective_from.isoformat(),
                    "validation_status": validation.status.value,
                    "version": fact.version,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="household.fact.create",
                resource_type="HOUSEHOLD_FACT",
                resource_id=fact.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="CASE_MANAGEMENT",
                metadata={
                    "event_id": str(event_id),
                    "source_type": source.source_type.value,
                    "validation_status": validation.status.value,
                },
            )
        )
        return fact


class ChangeFactValidationHandler:
    def __init__(
        self,
        *,
        facts: HouseholdFactRepository,
        validations: FactValidationRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._facts = facts
        self._validations = validations
        self._events = events
        self._audits = audits

    async def handle(
        self,
        command: ChangeFactValidationCommand,
    ) -> FactValidationState:
        fact = await self._facts.get_for_household(
            household_id=command.household_id,
            fact_id=command.fact_id,
        )
        if fact is None:
            raise HouseholdFactNotFoundError(str(command.fact_id))

        previous = await self._validations.get_state(fact.id)
        if previous is None:
            raise RuntimeError("Fact validation state is missing.")
        if previous.version != command.expected_validation_version:
            raise ProjectionVersionConflictError("Fact validation version changed.")

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
            FactValidationStatus.VALIDATED: "HouseholdFactValidated",
            FactValidationStatus.DISPUTED: "HouseholdFactDisputed",
            FactValidationStatus.REJECTED: "HouseholdFactRejected",
            FactValidationStatus.SUPERSEDED: "HouseholdFactSuperseded",
            FactValidationStatus.PENDING_VALIDATION: "HouseholdFactValidationPending",
        }[current.status]
        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type=event_type,
                event_version=1,
                aggregate_type="HOUSEHOLD_FACT",
                aggregate_id=fact.id,
                aggregate_version=current.version,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "fact_id": str(fact.id),
                    "household_id": str(fact.household_id),
                    "fact_type": fact.fact_type,
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
                action="household.fact.validation.change",
                resource_type="HOUSEHOLD_FACT",
                resource_id=fact.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="DATA_VALIDATION",
                metadata={
                    "event_id": str(event_id),
                    "from_status": previous.status.value,
                    "to_status": current.status.value,
                    "validation_version": current.version,
                    "reason_code": command.reason_code,
                },
            )
        )
        return current


class ResolveAcceptedFactHandler:
    def __init__(
        self,
        *,
        facts: HouseholdFactRepository,
        validations: FactValidationRepository,
        accepted_state: AcceptedStateRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._facts = facts
        self._validations = validations
        self._accepted_state = accepted_state
        self._events = events
        self._audits = audits

    async def handle(
        self,
        command: ResolveAcceptedFactCommand,
    ) -> CurrentAcceptedFact:
        fact = await self._facts.get_for_household(
            household_id=command.household_id,
            fact_id=command.fact_id,
        )
        if fact is None:
            raise HouseholdFactNotFoundError(str(command.fact_id))
        if fact.fact_type != command.fact_type:
            raise FactTypeMismatchError(command.fact_type)

        validation = await self._validations.get_state(fact.id)
        if validation is None or validation.status is not FactValidationStatus.VALIDATED:
            raise FactNotValidatedError(str(fact.id))

        previous = await self._accepted_state.get(
            household_id=command.household_id,
            fact_type=command.fact_type,
        )
        actual_version = 0 if previous is None else previous.projection_version
        if actual_version != command.expected_projection_version:
            raise ProjectionVersionConflictError("Accepted-state projection changed.")

        now = datetime.now(UTC)
        projection = CurrentAcceptedFact(
            household_id=command.household_id,
            fact_type=command.fact_type,
            fact_id=fact.id,
            accepted_value=fact.value,
            source_id=fact.source_id,
            effective_from=fact.effective_from,
            projection_version=actual_version + 1,
            projected_at=now,
            changed_by=command.actor_id,
        )

        event_id = uuid4()
        await self._accepted_state.set_current(
            accepted=projection,
            previous_fact_id=None if previous is None else previous.fact_id,
            reason_code=command.reason_code,
            reason_text=command.reason_text,
            event_id=event_id,
        )
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="CurrentAcceptedStateChanged",
                event_version=1,
                aggregate_type="HOUSEHOLD",
                aggregate_id=command.household_id,
                aggregate_version=projection.projection_version,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "household_id": str(command.household_id),
                    "fact_type": command.fact_type,
                    "previous_fact_id": (
                        None if previous is None else str(previous.fact_id)
                    ),
                    "new_fact_id": str(fact.id),
                    "projection_version": projection.projection_version,
                    "reason_code": command.reason_code,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="household.accepted_state.resolve",
                resource_type="HOUSEHOLD",
                resource_id=command.household_id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="DATA_VALIDATION",
                metadata={
                    "event_id": str(event_id),
                    "fact_type": command.fact_type,
                    "new_fact_id": str(fact.id),
                    "projection_version": projection.projection_version,
                },
            )
        )
        return projection
