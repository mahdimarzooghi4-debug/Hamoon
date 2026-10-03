from uuid import UUID

import pytest

from hamoon.domains.household.application.commands import CreateHouseholdCommand
from hamoon.domains.household.application.handlers import CreateHouseholdHandler
from hamoon.domains.household.domain.entities import CaseAssignment, Household
from hamoon.domains.household.domain.errors import HouseholdCaseCodeExistsError
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord


class FakeHouseholdRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, Household] = {}

    async def add(self, household: Household) -> None:
        self.items[household.id] = household

    async def get(self, household_id: UUID) -> Household | None:
        return self.items.get(household_id)

    async def get_by_case_code(self, case_code: str) -> Household | None:
        return next(
            (item for item in self.items.values() if item.case_code == case_code),
            None,
        )


class FakeAssignmentRepository:
    def __init__(self) -> None:
        self.items: list[CaseAssignment] = []

    async def add(self, assignment: CaseAssignment) -> None:
        self.items.append(assignment)

    async def has_active_assignment(
        self,
        *,
        household_id: UUID,
        actor_id: UUID,
    ) -> bool:
        return any(
            item.household_id == household_id and item.actor_id == actor_id
            for item in self.items
        )


class FakeEventRecorder:
    def __init__(self) -> None:
        self.items: list[DomainEventRecord] = []

    async def record(self, event: DomainEventRecord) -> None:
        self.items.append(event)


class FakeAuditRecorder:
    def __init__(self) -> None:
        self.items: list[AuditRecord] = []

    async def record(self, audit: AuditRecord) -> None:
        self.items.append(audit)


@pytest.mark.asyncio
async def test_create_household_creates_primary_assignment_event_and_audit() -> None:
    households = FakeHouseholdRepository()
    assignments = FakeAssignmentRepository()
    events = FakeEventRecorder()
    audits = FakeAuditRecorder()
    handler = CreateHouseholdHandler(
        households=households,
        assignments=assignments,
        events=events,
        audits=audits,
    )
    actor_id = UUID("11111111-1111-1111-1111-111111111111")

    household = await handler.handle(
        CreateHouseholdCommand(
            case_code="H-TEST-100",
            actor_id=actor_id,
            organizational_unit_id="unit-12",
            request_id="req-1",
            correlation_id="corr-1",
        )
    )

    assert household.primary_caseworker_id == actor_id
    assert household.organizational_unit_id == "unit-12"
    assert len(assignments.items) == 1
    assert assignments.items[0].actor_id == actor_id
    assert events.items[0].event_type == "HouseholdCreated"
    assert audits.items[0].action == "household.case.create"


@pytest.mark.asyncio
async def test_duplicate_case_code_is_rejected() -> None:
    households = FakeHouseholdRepository()
    assignments = FakeAssignmentRepository()
    events = FakeEventRecorder()
    audits = FakeAuditRecorder()
    handler = CreateHouseholdHandler(
        households=households,
        assignments=assignments,
        events=events,
        audits=audits,
    )
    actor_id = UUID("11111111-1111-1111-1111-111111111111")
    command = CreateHouseholdCommand(
        case_code="H-DUP",
        actor_id=actor_id,
        organizational_unit_id=None,
        request_id="req-1",
        correlation_id="corr-1",
    )

    await handler.handle(command)

    with pytest.raises(HouseholdCaseCodeExistsError):
        await handler.handle(command)

    assert len(assignments.items) == 1
    assert len(events.items) == 1
