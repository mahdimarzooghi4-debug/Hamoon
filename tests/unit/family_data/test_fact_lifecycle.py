from datetime import UTC, datetime
from uuid import UUID

import pytest

from hamoon.domains.family_data.application.commands import (
    ChangeFactValidationCommand,
    RecordHouseholdFactCommand,
    ResolveAcceptedFactCommand,
)
from hamoon.domains.family_data.application.handlers import (
    ChangeFactValidationHandler,
    RecordHouseholdFactHandler,
    ResolveAcceptedFactHandler,
)
from hamoon.domains.family_data.domain.entities import (
    CurrentAcceptedFact,
    DataSource,
    FactValidationState,
    FactValidationStatus,
    FactValueType,
    HouseholdFact,
    SourceType,
)
from hamoon.domains.family_data.domain.errors import FactNotValidatedError
from hamoon.domains.operations.domain.entities import (
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD_ID = UUID("22222222-2222-2222-2222-222222222222")
SOURCE_ID = UUID("00000000-0000-0000-0000-000000000103")


class FakeSourceRepository:
    async def get(self, source_id: UUID) -> DataSource | None:
        if source_id != SOURCE_ID:
            return None
        return DataSource(
            id=SOURCE_ID,
            code="EXTERNAL_DATA",
            source_type=SourceType.EXTERNAL_DATA,
            name="External data",
            active=True,
        )

    async def list_active(self) -> list[DataSource]:
        source = await self.get(SOURCE_ID)
        return [] if source is None else [source]


class FakeFactRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, HouseholdFact] = {}

    async def add(self, fact: HouseholdFact) -> None:
        self.items[fact.id] = fact

    async def get_for_household(
        self,
        *,
        household_id: UUID,
        fact_id: UUID,
    ) -> HouseholdFact | None:
        item = self.items.get(fact_id)
        if item is None or item.household_id != household_id:
            return None
        return item

    async def list_for_household(self, household_id: UUID) -> list[HouseholdFact]:
        return [
            item for item in self.items.values() if item.household_id == household_id
        ]


class FakeValidationRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, FactValidationState] = {}

    async def create_initial(
        self,
        *,
        state: FactValidationState,
        occurred_at: datetime,
    ) -> None:
        self.items[state.fact_id] = state

    async def get_state(self, fact_id: UUID) -> FactValidationState | None:
        return self.items.get(fact_id)

    async def transition(
        self,
        *,
        previous: FactValidationState,
        current: FactValidationState,
    ) -> None:
        assert self.items[previous.fact_id].version == previous.version
        self.items[current.fact_id] = current


class FakeAcceptedStateRepository:
    def __init__(self) -> None:
        self.items: dict[tuple[UUID, str], CurrentAcceptedFact] = {}

    async def get(
        self,
        *,
        household_id: UUID,
        fact_type: str,
    ) -> CurrentAcceptedFact | None:
        return self.items.get((household_id, fact_type))

    async def list_for_household(
        self,
        household_id: UUID,
    ) -> list[CurrentAcceptedFact]:
        return [
            item for (hid, _), item in self.items.items() if hid == household_id
        ]

    async def set_current(
        self,
        *,
        accepted: CurrentAcceptedFact,
        previous_fact_id: UUID | None,
        reason_code: str,
        reason_text: str | None,
        event_id: UUID,
    ) -> None:
        self.items[(accepted.household_id, accepted.fact_type)] = accepted


class FakeWorkItems:
    def __init__(self) -> None:
        self.items: dict[UUID, WorkItem] = {}

    async def get_by_resource(
        self,
        *,
        work_type: WorkItemType,
        resource_type: str,
        resource_id: UUID,
    ) -> WorkItem | None:
        return next(
            (
                item
                for item in self.items.values()
                if item.work_type is work_type
                and item.resource_type == resource_type
                and item.resource_id == resource_id
            ),
            None,
        )

    async def add(self, item: WorkItem) -> None:
        self.items[item.id] = item

    async def update(self, item: WorkItem, *, expected_version: int) -> None:
        current = self.items[item.id]
        assert current.version == expected_version
        self.items[item.id] = item


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


def make_record_handler(
    facts: FakeFactRepository,
    validations: FakeValidationRepository,
    events: FakeEventRecorder,
    audits: FakeAuditRecorder,
) -> RecordHouseholdFactHandler:
    return RecordHouseholdFactHandler(
        sources=FakeSourceRepository(),
        facts=facts,
        validations=validations,
        events=events,
        audits=audits,
    )


@pytest.mark.asyncio
async def test_authorized_external_source_is_not_accepted_by_default() -> None:
    facts = FakeFactRepository()
    validations = FakeValidationRepository()
    events = FakeEventRecorder()
    audits = FakeAuditRecorder()

    fact = await make_record_handler(facts, validations, events, audits).handle(
        RecordHouseholdFactCommand(
            household_id=HOUSEHOLD_ID,
            actor_id=ACTOR_ID,
            fact_type="EMPLOYMENT_STATUS",
            value_type=FactValueType.CODE,
            value="UNEMPLOYED",
            source_id=SOURCE_ID,
            source_detail="external registry",
            effective_from=datetime.now(UTC),
            request_id="req-1",
            correlation_id="corr-1",
        )
    )

    state = await validations.get_state(fact.id)
    assert state is not None
    assert state.status is FactValidationStatus.PENDING_VALIDATION
    assert events.items[0].payload["validation_status"] == "PENDING_VALIDATION"


@pytest.mark.asyncio
async def test_pending_fact_cannot_become_current_accepted_state() -> None:
    facts = FakeFactRepository()
    validations = FakeValidationRepository()
    events = FakeEventRecorder()
    audits = FakeAuditRecorder()

    fact = await make_record_handler(facts, validations, events, audits).handle(
        RecordHouseholdFactCommand(
            household_id=HOUSEHOLD_ID,
            actor_id=ACTOR_ID,
            fact_type="EMPLOYMENT_STATUS",
            value_type=FactValueType.CODE,
            value="UNEMPLOYED",
            source_id=SOURCE_ID,
            source_detail=None,
            effective_from=datetime.now(UTC),
            request_id="req-1",
            correlation_id="corr-1",
        )
    )

    handler = ResolveAcceptedFactHandler(
        facts=facts,
        validations=validations,
        accepted_state=FakeAcceptedStateRepository(),
        events=events,
        audits=audits,
    )

    with pytest.raises(FactNotValidatedError):
        await handler.handle(
            ResolveAcceptedFactCommand(
                household_id=HOUSEHOLD_ID,
                fact_type="EMPLOYMENT_STATUS",
                fact_id=fact.id,
                actor_id=ACTOR_ID,
                expected_projection_version=0,
                reason_code="HUMAN_RESOLUTION",
                reason_text=None,
                request_id="req-2",
                correlation_id="corr-1",
            )
        )


@pytest.mark.asyncio
async def test_validated_fact_can_become_current_accepted_state() -> None:
    facts = FakeFactRepository()
    validations = FakeValidationRepository()
    events = FakeEventRecorder()
    audits = FakeAuditRecorder()
    accepted = FakeAcceptedStateRepository()

    fact = await make_record_handler(facts, validations, events, audits).handle(
        RecordHouseholdFactCommand(
            household_id=HOUSEHOLD_ID,
            actor_id=ACTOR_ID,
            fact_type="EMPLOYMENT_STATUS",
            value_type=FactValueType.CODE,
            value="UNEMPLOYED",
            source_id=SOURCE_ID,
            source_detail=None,
            effective_from=datetime.now(UTC),
            request_id="req-1",
            correlation_id="corr-1",
        )
    )

    validation_handler = ChangeFactValidationHandler(
        facts=facts,
        validations=validations,
        events=events,
        audits=audits,
    )
    await validation_handler.handle(
        ChangeFactValidationCommand(
            household_id=HOUSEHOLD_ID,
            fact_id=fact.id,
            actor_id=ACTOR_ID,
            to_status=FactValidationStatus.VALIDATED,
            expected_validation_version=1,
            reason_code="SOURCE_REVIEWED",
            reason_text=None,
            request_id="req-2",
            correlation_id="corr-1",
        )
    )

    projection = await ResolveAcceptedFactHandler(
        facts=facts,
        validations=validations,
        accepted_state=accepted,
        events=events,
        audits=audits,
    ).handle(
        ResolveAcceptedFactCommand(
            household_id=HOUSEHOLD_ID,
            fact_type="EMPLOYMENT_STATUS",
            fact_id=fact.id,
            actor_id=ACTOR_ID,
            expected_projection_version=0,
            reason_code="HUMAN_RESOLUTION",
            reason_text=None,
            request_id="req-3",
            correlation_id="corr-1",
        )
    )

    assert projection.fact_id == fact.id
    assert projection.projection_version == 1
    assert events.items[-1].event_type == "CurrentAcceptedStateChanged"


@pytest.mark.asyncio
async def test_disputed_household_fact_creates_and_resolves_conflict_task() -> None:
    facts = FakeFactRepository()
    validations = FakeValidationRepository()
    work_items = FakeWorkItems()
    events = FakeEventRecorder()
    audits = FakeAuditRecorder()

    fact = await make_record_handler(facts, validations, events, audits).handle(
        RecordHouseholdFactCommand(
            household_id=HOUSEHOLD_ID,
            actor_id=ACTOR_ID,
            fact_type="EMPLOYMENT_STATUS",
            value_type=FactValueType.CODE,
            value="UNEMPLOYED",
            source_id=SOURCE_ID,
            source_detail="conflicting registry",
            effective_from=datetime.now(UTC),
            request_id="req-conflict-1",
            correlation_id="corr-conflict",
        )
    )

    disputed = await ChangeFactValidationHandler(
        facts=facts,
        validations=validations,
        work_items=work_items,
        events=events,
        audits=audits,
    ).handle(
        ChangeFactValidationCommand(
            household_id=HOUSEHOLD_ID,
            fact_id=fact.id,
            actor_id=ACTOR_ID,
            to_status=FactValidationStatus.DISPUTED,
            expected_validation_version=1,
            reason_code="SOURCE_CONFLICT",
            reason_text=None,
            request_id="req-conflict-2",
            correlation_id="corr-conflict",
        )
    )
    assert disputed.status is FactValidationStatus.DISPUTED
    task = next(iter(work_items.items.values()))
    assert task.work_type is WorkItemType.CONFLICT_RESOLUTION
    assert task.resource_type == "HOUSEHOLD_FACT"
    assert task.resource_id == fact.id
    assert task.status is WorkItemStatus.OPEN

    resolved = await ChangeFactValidationHandler(
        facts=facts,
        validations=validations,
        work_items=work_items,
        events=events,
        audits=audits,
    ).handle(
        ChangeFactValidationCommand(
            household_id=HOUSEHOLD_ID,
            fact_id=fact.id,
            actor_id=ACTOR_ID,
            to_status=FactValidationStatus.VALIDATED,
            expected_validation_version=2,
            reason_code="CONFLICT_RESOLVED",
            reason_text=None,
            request_id="req-conflict-3",
            correlation_id="corr-conflict",
        )
    )
    assert resolved.status is FactValidationStatus.VALIDATED
    assert work_items.items[task.id].status is WorkItemStatus.COMPLETED
