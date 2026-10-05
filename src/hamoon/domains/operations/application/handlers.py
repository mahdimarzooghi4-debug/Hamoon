from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from hamoon.domains.assessment.domain.entities import Assessment
from hamoon.domains.assessment.ports.repositories import AssessmentRepository
from hamoon.domains.intervention.ports.repositories import InterventionRepository
from hamoon.domains.pgor.ports.repositories import (
    PGORDefinitionRepository,
    PGORSnapshotRepository,
)
from hamoon.domains.prescription.ports.repositories import PrescriptionRepository
from hamoon.domains.provider_result.ports.repositories import ProviderResultRepository
from hamoon.domains.referral.ports.repositories import ReferralRepository
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


class EnsureWorkItemHandler:
    def __init__(
        self,
        *,
        work_items: WorkItemRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._work_items = work_items
        self._events = events
        self._audits = audits

    async def handle(
        self,
        *,
        household_id: UUID,
        work_type: WorkItemType,
        resource_type: str,
        resource_id: UUID,
        title: str,
        reason: str,
        priority: int,
        actor_id: UUID,
        request_id: str,
        correlation_id: str,
        due_at: datetime | None = None,
        assigned_actor_id: UUID | None = None,
        policy_version: str | None = None,
    ) -> WorkItem:
        existing = await self._work_items.get_by_resource(
            work_type=work_type,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        if existing is not None:
            return existing

        now = datetime.now(UTC)
        item = WorkItem(
            id=uuid4(),
            household_id=household_id,
            work_type=work_type,
            resource_type=resource_type,
            resource_id=resource_id,
            title=title,
            reason=reason,
            priority=priority,
            status=WorkItemStatus.OPEN,
            version=1,
            due_at=due_at,
            assigned_actor_id=assigned_actor_id,
            policy_version=policy_version,
            created_at=now,
            created_by=actor_id,
        )
        await self._work_items.add(item)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="WorkItemCreated",
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
                    "household_id": str(household_id),
                    "work_item_id": str(item.id),
                    "work_type": work_type.value,
                    "resource_type": resource_type,
                    "resource_id": str(resource_id),
                    "assigned_actor_id": (
                        None
                        if assigned_actor_id is None
                        else str(assigned_actor_id)
                    ),
                    "due_at": None if due_at is None else due_at.isoformat(),
                    "policy_version": policy_version,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=actor_id,
                action="work_item.create",
                resource_type="WORK_ITEM",
                resource_id=item.id,
                request_id=request_id,
                correlation_id=correlation_id,
                created_at=now,
                purpose="CASEWORKER_WORK_QUEUE",
                metadata={
                    "event_id": str(event_id),
                    "work_type": work_type.value,
                    "source_resource_type": resource_type,
                    "source_resource_id": str(resource_id),
                },
            )
        )
        return item


class CompleteWorkItemFromSourceHandler:
    def __init__(
        self,
        *,
        work_items: WorkItemRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._work_items = work_items
        self._events = events
        self._audits = audits

    async def handle(
        self,
        *,
        work_type: WorkItemType,
        resource_type: str,
        resource_id: UUID,
        actor_id: UUID,
        request_id: str,
        correlation_id: str,
    ) -> WorkItem | None:
        item = await self._work_items.get_by_resource(
            work_type=work_type,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        if item is None:
            return None
        if item.status in {WorkItemStatus.COMPLETED, WorkItemStatus.CANCELLED}:
            return item

        now = datetime.now(UTC)
        updated = item.complete_from_source(
            actor_id=actor_id,
            completed_at=now,
        )
        await self._work_items.update(updated, expected_version=item.version)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="WorkItemCompleted",
                event_version=1,
                aggregate_type="WORK_ITEM",
                aggregate_id=updated.id,
                aggregate_version=updated.version,
                actor_id=actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=correlation_id,
                causation_id=None,
                payload={
                    "household_id": str(updated.household_id),
                    "work_item_id": str(updated.id),
                    "work_type": updated.work_type.value,
                    "resource_type": updated.resource_type,
                    "resource_id": str(updated.resource_id),
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=actor_id,
                action="work_item.complete_from_source",
                resource_type="WORK_ITEM",
                resource_id=updated.id,
                request_id=request_id,
                correlation_id=correlation_id,
                created_at=now,
                purpose="CASEWORKER_WORK_QUEUE",
                metadata={
                    "event_id": str(event_id),
                    "work_type": updated.work_type.value,
                    "source_resource_type": updated.resource_type,
                    "source_resource_id": str(updated.resource_id),
                },
            )
        )
        return updated


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
            work_type=WorkItemType.REASSESSMENT_DUE,
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



class CreateReferralFollowupWorkItemHandler:
    POLICY_VERSION = "provider-response-timeout-v1"

    def __init__(
        self,
        *,
        work_items: WorkItemRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._work_items = work_items
        self._events = events
        self._audits = audits

    async def handle(
        self,
        *,
        referral_id: UUID,
        household_id: UUID,
        assigned_actor_id: UUID,
        due_at: datetime,
        actor_id: UUID,
        request_id: str,
        correlation_id: str,
    ) -> WorkItem:
        existing = await self._work_items.get_by_resource(
            work_type=WorkItemType.REFERRAL_FOLLOWUP,
            resource_type="REFERRAL",
            resource_id=referral_id,
        )
        if existing is not None:
            return existing

        now = datetime.now(UTC)
        item = WorkItem(
            id=uuid4(),
            household_id=household_id,
            work_type=WorkItemType.REFERRAL_FOLLOWUP,
            resource_type="REFERRAL",
            resource_id=referral_id,
            title="پیگیری عدم پاسخ ارائه‌دهنده",
            reason=(
                "مهلت پاسخ ارائه‌دهنده به ارجاع سپری شده و پاسخ معتبری "
                "دریافت نشده است."
            ),
            priority=80,
            status=WorkItemStatus.OPEN,
            version=1,
            due_at=due_at,
            assigned_actor_id=assigned_actor_id,
            policy_version=self.POLICY_VERSION,
            created_at=now,
            created_by=actor_id,
        )
        await self._work_items.add(item)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="ReferralFollowupWorkItemCreated",
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
                    "household_id": str(household_id),
                    "referral_id": str(referral_id),
                    "work_item_id": str(item.id),
                    "assigned_actor_id": str(assigned_actor_id),
                    "policy_version": item.policy_version,
                    "due_at": due_at.isoformat(),
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=actor_id,
                action="work_item.referral_followup.create",
                resource_type="WORK_ITEM",
                resource_id=item.id,
                request_id=request_id,
                correlation_id=correlation_id,
                created_at=now,
                purpose="CASEWORKER_WORK_QUEUE",
                metadata={
                    "event_id": str(event_id),
                    "referral_id": str(referral_id),
                    "assigned_actor_id": str(assigned_actor_id),
                    "policy_version": item.policy_version,
                },
            )
        )
        return item


class StartPlannedReassessmentHandler:
    def __init__(
        self,
        *,
        plans: ReassessmentPlanRepository,
        work_items: WorkItemRepository,
        assessments: AssessmentRepository,
        definitions: PGORDefinitionRepository,
        interventions: InterventionRepository,
        provider_results: ProviderResultRepository,
        referrals: ReferralRepository,
        prescriptions: PrescriptionRepository,
        snapshots: PGORSnapshotRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._plans = plans
        self._work_items = work_items
        self._assessments = assessments
        self._definitions = definitions
        self._interventions = interventions
        self._provider_results = provider_results
        self._referrals = referrals
        self._prescriptions = prescriptions
        self._snapshots = snapshots
        self._events = events
        self._audits = audits

    async def handle(
        self,
        *,
        work_item_id: UUID,
        expected_version: int,
        actor_id: UUID,
        request_id: str,
        correlation_id: str,
    ) -> tuple[Assessment, WorkItem, ReassessmentPlan]:
        from hamoon.domains.assessment.application.reassessment import (
            StartReassessmentHandler,
        )
        from hamoon.domains.assessment.domain.entities import AssessmentType

        item = await self._work_items.get(work_item_id)
        if item is None:
            raise LookupError("WORK_ITEM_NOT_FOUND")
        if item.work_type not in {
            WorkItemType.REASSESSMENT_DUE,
            WorkItemType.REASSESSMENT,
        }:
            raise ValueError("WORK_ITEM_NOT_REASSESSMENT")
        if item.resource_type != "REASSESSMENT_PLAN":
            raise ValueError("WORK_ITEM_RESOURCE_INVALID")
        if item.version != expected_version:
            raise ValueError("WORK_ITEM_VERSION_CONFLICT")

        plan = await self._plans.get(item.resource_id)
        if plan is None:
            raise LookupError("REASSESSMENT_PLAN_NOT_FOUND")
        if plan.post_assessment_id is not None:
            assessment = await self._assessments.get(plan.post_assessment_id)
            if assessment is None:
                raise RuntimeError("PLANNED_REASSESSMENT_MISSING")
            return assessment, item, plan

        prescription_item = await self._prescriptions.get_item_by_id(
            plan.prescription_item_id
        )
        if prescription_item is None:
            raise LookupError("PRESCRIPTION_ITEM_NOT_FOUND")
        prescription = await self._prescriptions.get(
            prescription_item.prescription_id
        )
        if prescription is None:
            raise LookupError("PRESCRIPTION_NOT_FOUND")
        pre_snapshot = await self._snapshots.get(prescription.pgor_snapshot_id)
        if pre_snapshot is None:
            raise LookupError("PRE_PGOR_SNAPSHOT_NOT_FOUND")
        pre_assessment = await self._assessments.get(pre_snapshot.assessment_id)
        if pre_assessment is None:
            raise LookupError("PRE_ASSESSMENT_NOT_FOUND")

        assessment = await StartReassessmentHandler(
            assessments=self._assessments,
            definitions=self._definitions,
            interventions=self._interventions,
            provider_results=self._provider_results,
            referrals=self._referrals,
            events=self._events,
            audits=self._audits,
        ).handle(
            household_id=plan.household_id,
            assessment_type=AssessmentType.OUTCOME_REASSESSMENT,
            definition_version_id=pre_assessment.definition_version_id,
            intervention_id=plan.intervention_id,
            provider_result_id=plan.provider_result_id,
            parent_assessment_id=pre_assessment.id,
            reason=(
                "Scheduled outcome re-assessment under "
                f"{plan.policy_version}"
            ),
            actor_id=actor_id,
            request_id=request_id,
            correlation_id=correlation_id,
        )

        updated_item = item
        if item.status is WorkItemStatus.OPEN:
            updated_item = item.claim(
                actor_id=actor_id,
                claimed_at=datetime.now(UTC),
            )
            await self._work_items.update(
                updated_item,
                expected_version=item.version,
            )
        elif (
            item.status is WorkItemStatus.CLAIMED
            and item.assigned_actor_id != actor_id
        ):
            raise ValueError("WORK_ITEM_ASSIGNED_TO_ANOTHER_ACTOR")

        updated_plan = plan.attach_reassessment(assessment_id=assessment.id)
        await self._plans.update(updated_plan, expected_version=plan.version)
        return assessment, updated_item, updated_plan


class MarkPostPGORReadyHandler:
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
        provider_result_id: UUID,
        assessment_id: UUID,
        snapshot_id: UUID,
        actor_id: UUID,
        request_id: str,
        correlation_id: str,
    ) -> ReassessmentPlan:
        plan = await self._plans.get_by_provider_result(provider_result_id)
        if plan is None:
            raise LookupError("REASSESSMENT_PLAN_NOT_FOUND")
        updated = plan.mark_post_pgor_ready(
            assessment_id=assessment_id,
            snapshot_id=snapshot_id,
        )
        if updated is not plan:
            await self._plans.update(updated, expected_version=plan.version)

        if plan.work_item_id is not None:
            item = await self._work_items.get(plan.work_item_id)
            if item is None:
                raise RuntimeError("REASSESSMENT_WORK_ITEM_MISSING")
            if item.status in {WorkItemStatus.OPEN, WorkItemStatus.CLAIMED}:
                completed = item.complete(
                    actor_id=actor_id,
                    completed_at=datetime.now(UTC),
                )
                await self._work_items.update(
                    completed,
                    expected_version=item.version,
                )

        now = datetime.now(UTC)
        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="ReassessmentPostPGORReady",
                event_version=1,
                aggregate_type="REASSESSMENT_PLAN",
                aggregate_id=updated.id,
                aggregate_version=updated.version,
                actor_id=actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=correlation_id,
                causation_id=None,
                payload={
                    "household_id": str(updated.household_id),
                    "reassessment_plan_id": str(updated.id),
                    "assessment_id": str(assessment_id),
                    "post_pgor_snapshot_id": str(snapshot_id),
                    "workflow_id": updated.workflow_id,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=actor_id,
                action="reassessment.post_pgor.ready",
                resource_type="REASSESSMENT_PLAN",
                resource_id=updated.id,
                request_id=request_id,
                correlation_id=correlation_id,
                created_at=now,
                purpose="OUTCOME_MEASUREMENT",
                metadata={
                    "event_id": str(event_id),
                    "assessment_id": str(assessment_id),
                    "post_pgor_snapshot_id": str(snapshot_id),
                },
            )
        )
        return updated


class CreateOutcomeReviewWorkItemHandler:
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
        outcome_id: UUID,
        actor_id: UUID,
        request_id: str,
        correlation_id: str,
    ) -> WorkItem:
        plan = await self._plans.get(plan_id)
        if plan is None:
            raise LookupError("REASSESSMENT_PLAN_NOT_FOUND")
        if plan.outcome_work_item_id is not None:
            existing = await self._work_items.get(plan.outcome_work_item_id)
            if existing is None:
                raise RuntimeError("OUTCOME_REVIEW_WORK_ITEM_MISSING")
            return existing

        now = datetime.now(UTC)
        item = WorkItem(
            id=uuid4(),
            household_id=plan.household_id,
            work_type=WorkItemType.OUTCOME_REVIEW,
            resource_type="HAMOON_OUTCOME",
            resource_id=outcome_id,
            title="مرور نتیجه و پیشنهاد هوش مصنوعی",
            reason=(
                "نتیجه بازسنجی و تفسیر ساختاریافته هوش مصنوعی "
                "برای تصمیم انسانی آماده است."
            ),
            priority=60,
            status=WorkItemStatus.OPEN,
            version=1,
            due_at=None,
            assigned_actor_id=plan.assigned_actor_id,
            policy_version=plan.policy_version,
            created_at=now,
            created_by=actor_id,
        )
        updated = plan.attach_outcome_review(
            outcome_id=outcome_id,
            work_item_id=item.id,
        )
        await self._work_items.add(item)
        await self._plans.update(updated, expected_version=plan.version)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="OutcomeReviewWorkItemCreated",
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
                    "household_id": str(plan.household_id),
                    "reassessment_plan_id": str(plan.id),
                    "outcome_id": str(outcome_id),
                    "work_item_id": str(item.id),
                    "assigned_actor_id": str(plan.assigned_actor_id),
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=actor_id,
                action="work_item.outcome_review.create",
                resource_type="WORK_ITEM",
                resource_id=item.id,
                request_id=request_id,
                correlation_id=correlation_id,
                created_at=now,
                purpose="HUMAN_OUTCOME_REVIEW",
                metadata={
                    "event_id": str(event_id),
                    "reassessment_plan_id": str(plan.id),
                    "outcome_id": str(outcome_id),
                },
            )
        )
        return item


class FinalizeOutcomeReviewHandler:
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
        outcome_id: UUID,
        actor_id: UUID,
        request_id: str,
        correlation_id: str,
    ) -> ReassessmentPlan | None:
        plan = await self._plans.get_by_outcome(outcome_id)
        if plan is None:
            return None
        if plan.status is ReassessmentPlanStatus.COMPLETED:
            return plan
        if plan.outcome_work_item_id is None:
            raise RuntimeError("OUTCOME_REVIEW_WORK_ITEM_MISSING")
        item = await self._work_items.get(plan.outcome_work_item_id)
        if item is None:
            raise RuntimeError("OUTCOME_REVIEW_WORK_ITEM_MISSING")
        if item.status in {WorkItemStatus.OPEN, WorkItemStatus.CLAIMED}:
            completed_item = item.complete(
                actor_id=actor_id,
                completed_at=datetime.now(UTC),
            )
            await self._work_items.update(
                completed_item,
                expected_version=item.version,
            )
        completed_plan = plan.complete()
        await self._plans.update(completed_plan, expected_version=plan.version)

        now = datetime.now(UTC)
        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="ReassessmentLoopCompleted",
                event_version=1,
                aggregate_type="REASSESSMENT_PLAN",
                aggregate_id=completed_plan.id,
                aggregate_version=completed_plan.version,
                actor_id=actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=correlation_id,
                causation_id=None,
                payload={
                    "household_id": str(completed_plan.household_id),
                    "reassessment_plan_id": str(completed_plan.id),
                    "outcome_id": str(outcome_id),
                    "workflow_id": completed_plan.workflow_id,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=actor_id,
                action="reassessment.loop.complete",
                resource_type="REASSESSMENT_PLAN",
                resource_id=completed_plan.id,
                request_id=request_id,
                correlation_id=correlation_id,
                created_at=now,
                purpose="OUTCOME_LEARNING_LOOP",
                metadata={
                    "event_id": str(event_id),
                    "outcome_id": str(outcome_id),
                },
            )
        )
        return completed_plan
