from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from hamoon.domains.operations.domain.entities import (
    ReassessmentPlan,
    ReassessmentPlanStatus,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)
from hamoon.domains.operations.ports import (
    ReassessmentPlanRepository,
    WorkItemRepository,
)
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder

REASSESSMENT_SCHEDULE_POLICY_VERSION = "prescription-item-review-v1"


class ScheduleReassessmentHandler:
    def __init__(
        self,
        *,
        plans: ReassessmentPlanRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._plans = plans
        self._events = events
        self._audits = audits

    async def handle(
        self,
        *,
        household_id: UUID,
        intervention_id: UUID,
        provider_result_id: UUID,
        prescription_item_id: UUID,
        assigned_actor_id: UUID,
        review_after_days: int,
        anchor_at: datetime,
        actor_id: UUID,
        request_id: str,
        correlation_id: str,
    ) -> ReassessmentPlan:
        existing = await self._plans.get_by_provider_result(provider_result_id)
        if existing is not None:
            return existing
        if review_after_days < 1:
            raise ValueError("REASSESSMENT_INTERVAL_INVALID")

        due_at = anchor_at + timedelta(days=review_after_days)
        now = datetime.now(UTC)
        plan_id = uuid4()
        plan = ReassessmentPlan(
            id=plan_id,
            household_id=household_id,
            intervention_id=intervention_id,
            provider_result_id=provider_result_id,
            prescription_item_id=prescription_item_id,
            assigned_actor_id=assigned_actor_id,
            review_after_days=review_after_days,
            due_at=due_at,
            policy_version=REASSESSMENT_SCHEDULE_POLICY_VERSION,
            workflow_id=f"reassessment:{plan_id}",
            status=ReassessmentPlanStatus.SCHEDULED,
            version=1,
            created_at=now,
            created_by=actor_id,
        )
        await self._plans.add(plan)
        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="ReassessmentScheduled",
                event_version=1,
                aggregate_type="REASSESSMENT_PLAN",
                aggregate_id=plan.id,
                aggregate_version=plan.version,
                actor_id=actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=correlation_id,
                causation_id=None,
                payload={
                    "household_id": str(household_id),
                    "reassessment_plan_id": str(plan.id),
                    "intervention_id": str(intervention_id),
                    "provider_result_id": str(provider_result_id),
                    "prescription_item_id": str(prescription_item_id),
                    "assigned_actor_id": str(assigned_actor_id),
                    "due_at": due_at.isoformat(),
                    "policy_version": plan.policy_version,
                    "workflow_id": plan.workflow_id,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=actor_id,
                action="reassessment.schedule",
                resource_type="REASSESSMENT_PLAN",
                resource_id=plan.id,
                request_id=request_id,
                correlation_id=correlation_id,
                created_at=now,
                purpose="OUTCOME_MEASUREMENT",
                metadata={
                    "event_id": str(event_id),
                    "provider_result_id": str(provider_result_id),
                    "due_at": due_at.isoformat(),
                    "policy_version": plan.policy_version,
                },
            )
        )
        return plan


class MaterializeReassessmentWorkItemHandler:
    def __init__(
        self,
        *,
        plans: ReassessmentPlanRepository,
        work_items: WorkItemRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._plans = plans
        self._work_items = work_items
        self._events = events
        self._audits = audits

    async def handle(
        self,
        *,
        plan_id: UUID,
        actor_id: UUID,
        request_id: str,
        correlation_id: str,
    ) -> WorkItem:
        plan = await self._plans.get(plan_id)
        if plan is None:
            raise LookupError("REASSESSMENT_PLAN_NOT_FOUND")
        if plan.work_item_id is not None:
            existing = await self._work_items.get(plan.work_item_id)
            if existing is None:
                raise RuntimeError("REASSESSMENT_WORK_ITEM_MISSING")
            return existing

        now = datetime.now(UTC)
        item = WorkItem(
            id=uuid4(),
            household_id=plan.household_id,
            work_type=WorkItemType.REASSESSMENT,
            resource_type="REASSESSMENT_PLAN",
            resource_id=plan.id,
            title="بازسنجی توانمندسازی خانوار",
            reason="زمان بازسنجی برنامه‌ریزی‌شده بر اساس مداخله ثبت‌شده فرا رسیده است.",
            priority=50,
            status=WorkItemStatus.OPEN,
            version=1,
            due_at=plan.due_at,
            assigned_actor_id=plan.assigned_actor_id,
            policy_version=plan.policy_version,
            created_at=now,
            created_by=actor_id,
        )
        updated = plan.attach_work_item(work_item_id=item.id, task_created_at=now)
        await self._work_items.add(item)
        await self._plans.update(updated, expected_version=plan.version)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="ReassessmentWorkItemCreated",
                event_version=1,
                aggregate_type="WORK_ITEM",
                aggregate_id=item.id,
                aggregate_version=item.version,
                actor_id=actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=correlation_id,
                causation_id=None,
                payload={
                    "household_id": str(item.household_id),
                    "work_item_id": str(item.id),
                    "reassessment_plan_id": str(plan.id),
                    "assigned_actor_id": str(plan.assigned_actor_id),
                    "due_at": plan.due_at.isoformat(),
                    "policy_version": plan.policy_version,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=actor_id,
                action="work_item.reassessment.create",
                resource_type="WORK_ITEM",
                resource_id=item.id,
                request_id=request_id,
                correlation_id=correlation_id,
                created_at=now,
                purpose="CASEWORKER_WORK_QUEUE",
                metadata={
                    "event_id": str(event_id),
                    "reassessment_plan_id": str(plan.id),
                    "assigned_actor_id": str(plan.assigned_actor_id),
                },
            )
        )
        return item
