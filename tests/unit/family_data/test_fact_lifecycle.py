from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4
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
from hamoon.domains.family_data.domain.errors import (
    CorrectionValueTypeMismatchError,
    FactNotValidatedError,
    FactTypeMismatchError,
    HouseholdFactNotFoundError,
    InvalidCorrectionLinkError,
    ProjectionVersionConflictError,
)
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
    accepted: FakeAcceptedStateRepository | None = None,
) -> RecordHouseholdFactHandler:
    return RecordHouseholdFactHandler(
        sources=FakeSourceRepository(),
        facts=facts,
        validations=validations,
        events=events,
        audits=audits,
        accepted_state=accepted,
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



def _correction_fixture() -> tuple[
    FakeFactRepository, FakeValidationRepository, FakeAcceptedStateRepository,
    FakeEventRecorder, FakeAuditRecorder, HouseholdFact,
]:
    facts = FakeFactRepository()
    validations = FakeValidationRepository()
    accepted = FakeAcceptedStateRepository()
    events = FakeEventRecorder()
    audits = FakeAuditRecorder()
    previous = HouseholdFact(
        id=uuid4(),
        household_id=HOUSEHOLD_ID,
        fact_type="EMPLOYMENT_STATUS",
        value_type=FactValueType.CODE,
        value="OLD",
        source_id=SOURCE_ID,
        effective_from=datetime.now(UTC),
        recorded_at=datetime.now(UTC),
        recorded_by=ACTOR_ID,
    )
    facts.items[previous.id] = previous
    accepted.items[(HOUSEHOLD_ID, "EMPLOYMENT_STATUS")] = CurrentAcceptedFact(
        household_id=HOUSEHOLD_ID,
        fact_type="EMPLOYMENT_STATUS",
        fact_id=previous.id,
        accepted_value=previous.value,
        source_id=SOURCE_ID,
        effective_from=previous.effective_from,
        projection_version=3,
        projected_at=datetime.now(UTC),
        changed_by=ACTOR_ID,
    )
    return facts, validations, accepted, events, audits, previous


def _correction_command(previous: HouseholdFact) -> RecordHouseholdFactCommand:
    return RecordHouseholdFactCommand(
        household_id=HOUSEHOLD_ID,
        actor_id=ACTOR_ID,
        fact_type="EMPLOYMENT_STATUS",
        value_type=FactValueType.CODE,
        value="NEW",
        source_id=SOURCE_ID,
        source_detail="reviewed source",
        effective_from=datetime.now(UTC),
        request_id="req-correction",
        correlation_id="corr-correction",
        supersedes_fact_id=previous.id,
        expected_accepted_projection_version=3,
        correction_reason_code="NEW_EVIDENCE",
        correction_reason_text="Human reviewed evidence",
    )


@pytest.mark.asyncio
async def test_linked_correction_is_persisted_pending_without_mutating_accepted_state() -> None:
    facts, validations, accepted, events, audits, previous = _correction_fixture()
    before = accepted.items[(HOUSEHOLD_ID, "EMPLOYMENT_STATUS")]
    fact = await make_record_handler(
        facts, validations, events, audits, accepted
    ).handle(_correction_command(previous))

    assert fact.supersedes_fact_id == previous.id
    assert fact.correction_reason_code == "NEW_EVIDENCE"
    assert fact.correction_reason_text == "Human reviewed evidence"
    assert fact.value == "NEW"
    assert facts.items[previous.id] == previous
    assert accepted.items[(HOUSEHOLD_ID, "EMPLOYMENT_STATUS")] == before
    state = await validations.get_state(fact.id)
    assert state is not None
    assert state.status is FactValidationStatus.PENDING_VALIDATION
    assert events.items[0].payload["supersedes_fact_id"] == str(previous.id)
    assert events.items[0].payload["correction_reason_code"] == "NEW_EVIDENCE"
    assert audits.items[0].metadata["supersedes_fact_id"] == str(previous.id)
    assert "Human reviewed evidence" not in str(audits.items[0].metadata)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("variant", "error_type"),
    [
        ("foreign_household", HouseholdFactNotFoundError),
        ("wrong_type", FactTypeMismatchError),
        ("wrong_value_type", CorrectionValueTypeMismatchError),
        ("stale_version", ProjectionVersionConflictError),
        ("different_current_fact", ProjectionVersionConflictError),
        ("missing_reason", InvalidCorrectionLinkError),
        ("missing_link", InvalidCorrectionLinkError),
    ],
)
async def test_invalid_correction_fails_without_writes(
    variant: str, error_type: type[Exception]
) -> None:
    facts, validations, accepted, events, audits, previous = _correction_fixture()
    command = _correction_command(previous)
    if variant == "foreign_household":
        foreign = replace(previous, id=uuid4(), household_id=uuid4())
        facts.items[foreign.id] = foreign
        command = replace(command, supersedes_fact_id=foreign.id)
    elif variant == "wrong_type":
        other = replace(previous, id=uuid4(), fact_type="OTHER")
        facts.items[other.id] = other
        command = replace(command, supersedes_fact_id=other.id)
    elif variant == "wrong_value_type":
        command = replace(command, value_type=FactValueType.STRING)
    elif variant == "stale_version":
        command = replace(command, expected_accepted_projection_version=2)
    elif variant == "different_current_fact":
        accepted.items[(HOUSEHOLD_ID, "EMPLOYMENT_STATUS")] = replace(
            accepted.items[(HOUSEHOLD_ID, "EMPLOYMENT_STATUS")], fact_id=uuid4()
        )
    elif variant == "missing_reason":
        command = replace(command, correction_reason_text=None)
    elif variant == "missing_link":
        command = replace(command, supersedes_fact_id=None)

    with pytest.raises(error_type):
        await make_record_handler(
            facts, validations, events, audits, accepted
        ).handle(command)
    assert len(facts.items) == (2 if variant == "foreign_household" or variant == "wrong_type" else 1)
    assert validations.items == {}
    assert events.items == []
    assert audits.items == []


def test_correction_api_schema_requires_link_version_and_reason_together() -> None:
    from pydantic import ValidationError
    from hamoon.domains.family_data.api.schemas import RecordFactRequest

    previous = uuid4()
    payload = {
        "fact_type": "employment_status",
        "value_type": "CODE",
        "value": "NEW",
        "source_id": SOURCE_ID,
        "effective_from": datetime.now(UTC),
        "supersedes_fact_id": previous,
        "expected_accepted_projection_version": 3,
        "correction_reason_code": "NEW_EVIDENCE",
        "correction_reason_text": "Human reviewed evidence",
    }
    valid = RecordFactRequest.model_validate(payload)
    assert valid.fact_type == "EMPLOYMENT_STATUS"
    assert valid.supersedes_fact_id == previous

    for field in (
        "supersedes_fact_id",
        "expected_accepted_projection_version",
        "correction_reason_code",
        "correction_reason_text",
    ):
        with pytest.raises(ValidationError):
            RecordFactRequest.model_validate({
                key: value for key, value in payload.items() if key != field
            })
    with pytest.raises(ValidationError):
        RecordFactRequest.model_validate({
            **payload, "correction_reason_text": "   "
        })
    # Existing unlinked fact-record contract remains valid.
    unlinked = RecordFactRequest.model_validate({
        key: value for key, value in payload.items()
        if key not in (
            "supersedes_fact_id",
            "expected_accepted_projection_version",
            "correction_reason_code",
            "correction_reason_text",
        )
    })
    assert unlinked.supersedes_fact_id is None
