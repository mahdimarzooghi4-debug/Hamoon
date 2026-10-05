from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from hamoon.domains.operations.application.handlers import (
    CompleteWorkItemFromSourceHandler,
    EnsureWorkItemHandler,
)
from hamoon.domains.operations.domain.entities import (
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)

ACTOR = UUID("11111111-1111-1111-1111-111111111111")
OTHER_ACTOR = UUID("22222222-2222-2222-2222-222222222222")
HOUSEHOLD = UUID("33333333-3333-3333-3333-333333333333")
RESOURCE = UUID("44444444-4444-4444-4444-444444444444")


class WorkItems:
    def __init__(self) -> None:
        self.items: dict[UUID, WorkItem] = {}

    async def add(self, item: WorkItem) -> None:
        self.items[item.id] = item

    async def get(self, work_item_id: UUID) -> WorkItem | None:
        return self.items.get(work_item_id)

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

    async def update(
        self,
        item: WorkItem,
        *,
        expected_version: int,
    ) -> None:
        current = self.items[item.id]
        assert current.version == expected_version
        self.items[item.id] = item


class Recorder:
    def __init__(self) -> None:
        self.items: list[object] = []

    async def record(self, item: object) -> None:
        self.items.append(item)


@pytest.mark.asyncio
async def test_work_item_projection_is_idempotent_and_source_linked() -> None:
    work_items = WorkItems()
    events = Recorder()
    audits = Recorder()
    handler = EnsureWorkItemHandler(
        work_items=work_items,
        events=events,
        audits=audits,
    )

    first = await handler.handle(
        household_id=HOUSEHOLD,
        work_type=WorkItemType.DIAGNOSIS_REVIEW,
        resource_type="DIAGNOSIS",
        resource_id=RESOURCE,
        title="review",
        reason="human review required",
        priority=70,
        actor_id=ACTOR,
        request_id="req-1",
        correlation_id="corr-1",
        policy_version="diagnosis-review-v1",
    )
    second = await handler.handle(
        household_id=HOUSEHOLD,
        work_type=WorkItemType.DIAGNOSIS_REVIEW,
        resource_type="DIAGNOSIS",
        resource_id=RESOURCE,
        title="ignored duplicate",
        reason="ignored duplicate",
        priority=1,
        actor_id=ACTOR,
        request_id="req-2",
        correlation_id="corr-2",
    )

    assert second.id == first.id
    assert len(work_items.items) == 1
    assert first.assigned_actor_id is None
    assert first.resource_id == RESOURCE
    assert first.status is WorkItemStatus.OPEN
    assert len(events.items) == 1
    assert len(audits.items) == 1


@pytest.mark.asyncio
async def test_source_completion_closes_claimed_task_even_if_reviewer_changed() -> None:
    work_items = WorkItems()
    events = Recorder()
    audits = Recorder()
    item = WorkItem(
        id=UUID("55555555-5555-5555-5555-555555555555"),
        household_id=HOUSEHOLD,
        work_type=WorkItemType.PRESCRIPTION_REVIEW,
        resource_type="PRESCRIPTION",
        resource_id=RESOURCE,
        title="review",
        reason="human review required",
        priority=70,
        status=WorkItemStatus.CLAIMED,
        version=2,
        due_at=None,
        assigned_actor_id=OTHER_ACTOR,
        policy_version="prescription-review-v1",
        created_at=datetime.now(UTC),
        created_by=ACTOR,
        claimed_at=datetime.now(UTC),
        claimed_by=OTHER_ACTOR,
    )
    work_items.items[item.id] = item

    completed = await CompleteWorkItemFromSourceHandler(
        work_items=work_items,
        events=events,
        audits=audits,
    ).handle(
        work_type=WorkItemType.PRESCRIPTION_REVIEW,
        resource_type="PRESCRIPTION",
        resource_id=RESOURCE,
        actor_id=ACTOR,
        request_id="req-complete",
        correlation_id="corr-complete",
    )

    assert completed is not None
    assert completed.status is WorkItemStatus.COMPLETED
    assert completed.completed_by == ACTOR
    assert completed.assigned_actor_id == OTHER_ACTOR
    assert completed.version == 3
    assert len(events.items) == 1
    assert len(audits.items) == 1


def test_work_item_source_completion_is_noop_for_cancelled_task() -> None:
    item = WorkItem(
        id=UUID("66666666-6666-6666-6666-666666666666"),
        household_id=HOUSEHOLD,
        work_type=WorkItemType.CONFLICT_RESOLUTION,
        resource_type="INDICATOR_OBSERVATION",
        resource_id=RESOURCE,
        title="conflict",
        reason="disputed",
        priority=80,
        status=WorkItemStatus.CANCELLED,
        version=4,
        due_at=None,
        assigned_actor_id=None,
        policy_version="observation-conflict-v1",
        created_at=datetime.now(UTC),
        created_by=ACTOR,
    )

    assert item.complete_from_source(
        actor_id=ACTOR,
        completed_at=datetime.now(UTC),
    ) is item
