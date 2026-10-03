from datetime import UTC, datetime
from uuid import uuid4

from hamoon.domains.household.application.commands import CreateHouseholdCommand
from hamoon.domains.household.domain.entities import (
    CaseAssignment,
    CaseAssignmentType,
    Household,
    HouseholdStatus,
)
from hamoon.domains.household.domain.errors import HouseholdCaseCodeExistsError
from hamoon.domains.household.ports.repositories import (
    CaseAssignmentRepository,
    HouseholdRepository,
)
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder


class CreateHouseholdHandler:
    def __init__(
        self,
        *,
        households: HouseholdRepository,
        assignments: CaseAssignmentRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._households = households
        self._assignments = assignments
        self._events = events
        self._audits = audits

    async def handle(self, command: CreateHouseholdCommand) -> Household:
        existing = await self._households.get_by_case_code(command.case_code)
        if existing is not None:
            raise HouseholdCaseCodeExistsError(command.case_code)

        now = datetime.now(UTC)
        household_id = uuid4()
        household = Household(
            id=household_id,
            case_code=command.case_code,
            lifecycle_status=HouseholdStatus.DRAFT,
            organizational_unit_id=command.organizational_unit_id,
            primary_caseworker_id=command.actor_id,
            version=1,
            created_at=now,
            created_by=command.actor_id,
        )
        assignment = CaseAssignment(
            id=uuid4(),
            household_id=household_id,
            actor_id=command.actor_id,
            assignment_type=CaseAssignmentType.PRIMARY,
            valid_from=now,
            valid_to=None,
            assigned_by=command.actor_id,
            reason="HOUSEHOLD_CREATION",
            created_at=now,
        )

        await self._households.add(household)
        await self._assignments.add(assignment)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="HouseholdCreated",
                event_version=1,
                aggregate_type="HOUSEHOLD",
                aggregate_id=household.id,
                aggregate_version=household.version,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "household_id": str(household.id),
                    "case_code": household.case_code,
                    "organizational_unit_id": household.organizational_unit_id,
                    "primary_caseworker_id": str(command.actor_id),
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="household.case.create",
                resource_type="HOUSEHOLD",
                resource_id=household.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                purpose="CASE_MANAGEMENT",
                metadata={"event_id": str(event_id)},
                created_at=now,
            )
        )
        return household
