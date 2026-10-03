from datetime import datetime
from typing import Protocol
from uuid import UUID

from hamoon.domains.operations.domain.entities import (
    ReassessmentPlan,
    ReassessmentPlanStatus,
    WorkItem,
    WorkItemStatus,
)


class ReassessmentPlanRepository(Protocol):
    async def add(self, plan: ReassessmentPlan) -> None: ...

    async def get(self, plan_id: UUID) -> ReassessmentPlan | None: ...

    async def get_by_provider_result(
        self,
        provider_result_id: UUID,
    ) -> ReassessmentPlan | None: ...

    async def get_by_outcome(
        self,
        outcome_id: UUID,
    ) -> ReassessmentPlan | None: ...

    async def update(
        self,
        plan: ReassessmentPlan,
        *,
        expected_version: int,
    ) -> None: ...

    async def list_by_status(
        self,
        *,
        statuses: tuple[ReassessmentPlanStatus, ...],
        limit: int,
    ) -> list[ReassessmentPlan]: ...


class WorkItemRepository(Protocol):
    async def add(self, item: WorkItem) -> None: ...

    async def get(self, work_item_id: UUID) -> WorkItem | None: ...

    async def update(
        self,
        item: WorkItem,
        *,
        expected_version: int,
    ) -> None: ...

    async def list_for_actor(
        self,
        *,
        actor_id: UUID,
        statuses: tuple[WorkItemStatus, ...],
        due_before: datetime | None,
        limit: int,
    ) -> list[WorkItem]: ...
