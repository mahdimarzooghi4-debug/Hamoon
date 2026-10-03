from temporalio import activity

from hamoon.domains.operations.application.handlers import (
    MaterializeReassessmentWorkItemHandler,
)
from hamoon.domains.operations.infrastructure.repositories import (
    SqlAlchemyReassessmentPlanRepository,
    SqlAlchemyWorkItemRepository,
)
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import session_factory
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder
from hamoon.infrastructure.temporal.contracts import MaterializeReassessmentInput


@activity.defn(name="materialize_reassessment_work_item")
async def materialize_reassessment_work_item(
    data: MaterializeReassessmentInput,
) -> str:
    async with session_factory() as session:
        async with session.begin():
            item = await MaterializeReassessmentWorkItemHandler(
                plans=SqlAlchemyReassessmentPlanRepository(session),
                work_items=SqlAlchemyWorkItemRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                plan_id=data.plan_id,
                actor_id=data.actor_id,
                request_id=activity.info().activity_id,
                correlation_id=data.correlation_id,
            )
    return str(item.id)
