from datetime import UTC, datetime
from uuid import UUID

import pytest

from hamoon.domains.operations.application.handlers import (
    CreateOutcomeReviewWorkItemHandler,
    CreateReferralFollowupWorkItemHandler,
    FinalizeOutcomeReviewHandler,
    MarkPostPGORReadyHandler,
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

    async def get_by_outcome(self, outcome_id):
        if self.item is not None and self.item.outcome_id == outcome_id:
            return self.item
        return None

    async def update(self, plan, *, expected_version):
        assert self.item is not None
        assert self.item.version == expected_version
        self.item = plan

    async def list_by_status(self, *, statuses, limit):
        if self.item is None or self.item.status not in statuses:
            return []
        return [self.item][:limit]


class WorkItems:
    def __init__(self):
        self.item = None

    async def add(self, item):
        self.item = item

    async def get(self, work_item_id):
        return self.item if self.item is not None and self.item.id == work_item_id else None

    async def get_by_resource(self, *, work_type, resource_type, resource_id):
        if (
            self.item is not None
            and self.item.work_type is work_type
            and self.item.resource_type == resource_type
            and self.item.resource_id == resource_id
        ):
            return self.item
        return None

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

    assert work_item.work_type is WorkItemType.REASSESSMENT_DUE
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



@pytest.mark.asyncio
async def test_post_pgor_to_outcome_review_completes_operational_loop() -> None:
    plans = Plans()
    work_items = WorkItems()
    events = Recorder()
    audits = Recorder()
    plan = await ScheduleReassessmentHandler(
        plans=plans,
        events=events,
        audits=audits,
    ).handle(
        household_id=HOUSEHOLD,
        intervention_id=INTERVENTION,
        provider_result_id=RESULT,
        prescription_item_id=ITEM,
        assigned_actor_id=ACTOR,
        review_after_days=14,
        anchor_at=datetime(2026, 2, 1, tzinfo=UTC),
        actor_id=ACTOR,
        request_id="req",
        correlation_id="corr",
    )
    reassessment_work_item = await MaterializeReassessmentWorkItemHandler(
        plans=plans,
        work_items=work_items,
        events=events,
        audits=audits,
    ).handle(
        plan_id=plan.id,
        actor_id=ACTOR,
        request_id="activity",
        correlation_id=plan.workflow_id,
    )
    assessment_id = UUID("66666666-6666-6666-6666-666666666666")
    snapshot_id = UUID("77777777-7777-7777-7777-777777777777")
    outcome_id = UUID("88888888-8888-8888-8888-888888888888")

    started = plans.item.attach_reassessment(assessment_id=assessment_id)
    await plans.update(started, expected_version=plans.item.version)

    ready = await MarkPostPGORReadyHandler(
        plans=plans,
        work_items=work_items,
        events=events,
        audits=audits,
    ).handle(
        provider_result_id=RESULT,
        assessment_id=assessment_id,
        snapshot_id=snapshot_id,
        actor_id=ACTOR,
        request_id="pgor",
        correlation_id="corr",
    )
    assert ready.status is ReassessmentPlanStatus.POST_PGOR_READY
    assert ready.post_pgor_snapshot_id == snapshot_id
    assert work_items.item.id == reassessment_work_item.id
    assert work_items.item.status is WorkItemStatus.COMPLETED

    review_item = await CreateOutcomeReviewWorkItemHandler(
        plans=plans,
        work_items=work_items,
        events=events,
        audits=audits,
    ).handle(
        plan_id=plan.id,
        outcome_id=outcome_id,
        actor_id=ACTOR,
        request_id="outcome-ai",
        correlation_id=plan.workflow_id,
    )
    assert review_item.work_type is WorkItemType.OUTCOME_REVIEW
    assert plans.item.status is ReassessmentPlanStatus.OUTCOME_REVIEW
    assert plans.item.outcome_id == outcome_id

    completed = await FinalizeOutcomeReviewHandler(
        plans=plans,
        work_items=work_items,
        events=events,
        audits=audits,
    ).handle(
        outcome_id=outcome_id,
        actor_id=ACTOR,
        request_id="human-review",
        correlation_id="corr",
    )
    assert completed is not None
    assert completed.status is ReassessmentPlanStatus.COMPLETED
    assert work_items.item.status is WorkItemStatus.COMPLETED
    assert events.items[-1].event_type == "ReassessmentLoopCompleted"

@pytest.mark.asyncio
async def test_finalize_outcome_review_is_noop_for_independent_outcome() -> None:
    plans = Plans()
    work_items = WorkItems()
    events = Recorder()
    audits = Recorder()

    completed = await FinalizeOutcomeReviewHandler(
        plans=plans,
        work_items=work_items,
        events=events,
        audits=audits,
    ).handle(
        outcome_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        actor_id=ACTOR,
        request_id="human-review",
        correlation_id="corr",
    )

    assert completed is None
    assert work_items.item is None
    assert events.items == []
    assert audits.items == []



@pytest.mark.asyncio
async def test_referral_timeout_materializes_one_followup_work_item() -> None:
    referral_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    work_items = WorkItems()
    events = Recorder()
    audits = Recorder()
    handler = CreateReferralFollowupWorkItemHandler(
        work_items=work_items,
        events=events,
        audits=audits,
    )
    due_at = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)

    first = await handler.handle(
        referral_id=referral_id,
        household_id=HOUSEHOLD,
        assigned_actor_id=ACTOR,
        due_at=due_at,
        actor_id=ACTOR,
        request_id="timeout-activity",
        correlation_id="referral-workflow",
    )
    duplicate = await handler.handle(
        referral_id=referral_id,
        household_id=HOUSEHOLD,
        assigned_actor_id=ACTOR,
        due_at=due_at,
        actor_id=ACTOR,
        request_id="timeout-activity-retry",
        correlation_id="referral-workflow",
    )

    assert duplicate.id == first.id
    assert first.work_type is WorkItemType.REFERRAL_FOLLOWUP
    assert first.resource_type == "REFERRAL"
    assert first.resource_id == referral_id
    assert first.status is WorkItemStatus.OPEN
    assert first.assigned_actor_id == ACTOR
    assert first.due_at == due_at
    assert first.policy_version == "provider-response-timeout-v1"
    assert len(events.items) == 1
    assert events.items[0].event_type == "ReferralFollowupWorkItemCreated"
    assert len(audits.items) == 1
    assert audits.items[0].action == "work_item.referral_followup.create"
