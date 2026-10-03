from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.operations.domain.entities import (
    ReassessmentPlan,
    WorkItem,
    WorkItemStatus,
)
from hamoon.domains.operations.infrastructure.models import (
    ReassessmentPlanModel,
    WorkItemModel,
)


def _plan(model: ReassessmentPlanModel) -> ReassessmentPlan:
    return ReassessmentPlan(
        id=model.id,
        household_id=model.household_id,
        intervention_id=model.intervention_id,
        provider_result_id=model.provider_result_id,
        prescription_item_id=model.prescription_item_id,
        assigned_actor_id=model.assigned_actor_id,
        review_after_days=model.review_after_days,
        due_at=model.due_at,
        policy_version=model.policy_version,
        workflow_id=model.workflow_id,
        status=model.status,
        version=model.version,
        created_at=model.created_at,
        created_by=model.created_by,
        work_item_id=model.work_item_id,
        task_created_at=model.task_created_at,
    )


def _work_item(model: WorkItemModel) -> WorkItem:
    return WorkItem(
        id=model.id,
        household_id=model.household_id,
        work_type=model.work_type,
        resource_type=model.resource_type,
        resource_id=model.resource_id,
        title=model.title,
        reason=model.reason,
        priority=model.priority,
        status=model.status,
        version=model.version,
        due_at=model.due_at,
        assigned_actor_id=model.assigned_actor_id,
        policy_version=model.policy_version,
        created_at=model.created_at,
        created_by=model.created_by,
        claimed_at=model.claimed_at,
        claimed_by=model.claimed_by,
        completed_at=model.completed_at,
        completed_by=model.completed_by,
    )


class SqlAlchemyReassessmentPlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, plan: ReassessmentPlan) -> None:
        self._session.add(
            ReassessmentPlanModel(
                id=plan.id,
                household_id=plan.household_id,
                intervention_id=plan.intervention_id,
                provider_result_id=plan.provider_result_id,
                prescription_item_id=plan.prescription_item_id,
                assigned_actor_id=plan.assigned_actor_id,
                review_after_days=plan.review_after_days,
                due_at=plan.due_at,
                policy_version=plan.policy_version,
                workflow_id=plan.workflow_id,
                status=plan.status,
                version=plan.version,
                created_at=plan.created_at,
                created_by=plan.created_by,
                work_item_id=plan.work_item_id,
                task_created_at=plan.task_created_at,
            )
        )

    async def get(self, plan_id: UUID) -> ReassessmentPlan | None:
        model = await self._session.get(ReassessmentPlanModel, plan_id)
        return None if model is None else _plan(model)

    async def get_by_provider_result(
        self,
        provider_result_id: UUID,
    ) -> ReassessmentPlan | None:
        result = await self._session.execute(
            select(ReassessmentPlanModel).where(
                ReassessmentPlanModel.provider_result_id == provider_result_id
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else _plan(model)

    async def update(
        self,
        plan: ReassessmentPlan,
        *,
        expected_version: int,
    ) -> None:
        result = await self._session.execute(
            select(ReassessmentPlanModel)
            .where(ReassessmentPlanModel.id == plan.id)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise LookupError("REASSESSMENT_PLAN_NOT_FOUND")
        if model.version != expected_version:
            raise ValueError("REASSESSMENT_PLAN_VERSION_CONFLICT")
        model.status = plan.status
        model.version = plan.version
        model.work_item_id = plan.work_item_id
        model.task_created_at = plan.task_created_at


class SqlAlchemyWorkItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, item: WorkItem) -> None:
        self._session.add(
            WorkItemModel(
                id=item.id,
                household_id=item.household_id,
                work_type=item.work_type,
                resource_type=item.resource_type,
                resource_id=item.resource_id,
                title=item.title,
                reason=item.reason,
                priority=item.priority,
                status=item.status,
                version=item.version,
                due_at=item.due_at,
                assigned_actor_id=item.assigned_actor_id,
                policy_version=item.policy_version,
                created_at=item.created_at,
                created_by=item.created_by,
                claimed_at=item.claimed_at,
                claimed_by=item.claimed_by,
                completed_at=item.completed_at,
                completed_by=item.completed_by,
            )
        )

    async def get(self, work_item_id: UUID) -> WorkItem | None:
        model = await self._session.get(WorkItemModel, work_item_id)
        return None if model is None else _work_item(model)

    async def update(
        self,
        item: WorkItem,
        *,
        expected_version: int,
    ) -> None:
        result = await self._session.execute(
            select(WorkItemModel)
            .where(WorkItemModel.id == item.id)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise LookupError("WORK_ITEM_NOT_FOUND")
        if model.version != expected_version:
            raise ValueError("WORK_ITEM_VERSION_CONFLICT")
        model.status = item.status
        model.version = item.version
        model.assigned_actor_id = item.assigned_actor_id
        model.claimed_at = item.claimed_at
        model.claimed_by = item.claimed_by
        model.completed_at = item.completed_at
        model.completed_by = item.completed_by

    async def list_for_actor(
        self,
        *,
        actor_id: UUID,
        statuses: tuple[WorkItemStatus, ...],
        due_before: datetime | None,
        limit: int,
    ) -> list[WorkItem]:
        statement = select(WorkItemModel).where(
            or_(
                WorkItemModel.assigned_actor_id == actor_id,
                WorkItemModel.claimed_by == actor_id,
            )
        )
        if statuses:
            statement = statement.where(WorkItemModel.status.in_(statuses))
        if due_before is not None:
            statement = statement.where(WorkItemModel.due_at <= due_before)
        statement = statement.order_by(
            WorkItemModel.priority.desc(),
            WorkItemModel.due_at.asc().nulls_last(),
            WorkItemModel.created_at.asc(),
        ).limit(limit)
        result = await self._session.execute(statement)
        return [_work_item(model) for model in result.scalars().all()]
