from datetime import UTC, datetime
from uuid import UUID

import pytest

from hamoon.domains.operations.application.handlers import (
    MaterializeReassessmentWorkItemHandler,
    ScheduleReassessmentHandler,
)
from hamoon.domains.operations.domain.entities import (
    ReassessmentPlanStatus,
    WorkItemStatus,
    WorkItemType,
)

ACTOR = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD = UUID("22222222-2222-2222-2222-222222222222")
INTERVENTION = UUID("33333333-3333-3333-3333-333333333333")
RESULT = UUID("44444444-4444-4444-4444-444444444444")
ITEM = UUID("55555555-5555-5555-5555-555555555555")


class Plans:
    def __init__(self):
        self.item = None

    async def add(self, plan):
        self.item = plan

    async def get(self, plan_id):
        return self.item if self.item is not None and self.item.id == plan_id else None

    async def get_by_provider_result(self, provider_result_id):
        if self.item is not None and self.item.provider_result_id == provider_result_id:
            return self.item
        return None

    async def update(self, plan, *, expected_version):
        assert self.item is not None
        assert self.item.version == expected_version
        self.item = plan

    async def list_scheduled(self, *, limit):
        if self.item is None or self.item.status is not ReassessmentPlanStatus.SCHEDULED:
            return []
        return [self.item][:limit]


class WorkItems:
    def __init__(self):
        self.item = None

    async def add(self, item):
        self.item = item

    async def get(self, work_item_id):
        return self.item if self.item is not None and self.item.id == work_item_id else None

    async def update(self, item, *, expected_version):
        assert self.item is not None
        assert self.item.version == expected_version
        self.item = item

    async def list_for_actor(self, **kwargs):
        return [] if self.item is None else [self.item]


class Recorder:
    def __init__(self):
        self.items = []

    async def record(self, item):
        self.items.append(item)


@pytest.mark.asyncio
async def test_schedule_is_versioned_idempotent_and_materializes_work_item() -> None:
    plans = Plans()
    events = Recorder()
    audits = Recorder()
    anchor = datetime(2026, 1, 1, tzinfo=UTC)

    scheduler = ScheduleReassessmentHandler(
        plans=plans,
        events=events,
        audits=audits,
    )
    plan = await scheduler.handle(
        household_id=HOUSEHOLD,
        intervention_id=INTERVENTION,
        provider_result_id=RESULT,
        prescription_item_id=ITEM,
        assigned_actor_id=ACTOR,
        review_after_days=30,
        anchor_at=anchor,
        actor_id=ACTOR,
        request_id="req",
        correlation_id="corr",
    )
    duplicate = await scheduler.handle(
        household_id=HOUSEHOLD,
        intervention_id=INTERVENTION,
        provider_result_id=RESULT,
        prescription_item_id=ITEM,
        assigned_actor_id=ACTOR,
        review_after_days=30,
        anchor_at=anchor,
        actor_id=ACTOR,
        request_id="req",
        correlation_id="corr",
    )

    assert duplicate.id == plan.id
    assert plan.due_at == datetime(2026, 1, 31, tzinfo=UTC)
    assert plan.workflow_id == f"reassessment:{plan.id}"
    assert plan.policy_version == "prescription-item-review-v1"
    assert events.items[0].event_type == "ReassessmentScheduled"

    work_items = WorkItems()
    work_item = await MaterializeReassessmentWorkItemHandler(
        plans=plans,
        work_items=work_items,
        events=events,
        audits=audits,
    ).handle(
        plan_id=plan.id,
        actor_id=ACTOR,
        request_id="temporal-activity",
        correlation_id=plan.workflow_id,
    )

    assert work_item.work_type is WorkItemType.REASSESSMENT
    assert work_item.status is WorkItemStatus.OPEN
    assert work_item.assigned_actor_id == ACTOR
    assert work_item.due_at == plan.due_at
    assert plans.item.status is ReassessmentPlanStatus.TASK_CREATED
    assert plans.item.work_item_id == work_item.id
    assert events.items[-1].event_type == "ReassessmentWorkItemCreated"


def test_work_item_claim_enforces_assignment() -> None:
    from hamoon.domains.operations.domain.entities import WorkItem

    item = WorkItem(
        id=ITEM,
        household_id=HOUSEHOLD,
        work_type=WorkItemType.REASSESSMENT,
        resource_type="REASSESSMENT_PLAN",
        resource_id=RESULT,
        title="Reassessment",
        reason="Due",
        priority=50,
        status=WorkItemStatus.OPEN,
        version=1,
        due_at=None,
        assigned_actor_id=ACTOR,
        policy_version="v1",
        created_at=datetime.now(UTC),
        created_by=ACTOR,
    )
    other = UUID("99999999-9999-9999-9999-999999999999")
    with pytest.raises(ValueError, match="WORK_ITEM_ASSIGNED_TO_ANOTHER_ACTOR"):
        item.claim(actor_id=other, claimed_at=datetime.now(UTC))
