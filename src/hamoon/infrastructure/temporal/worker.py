import asyncio
import logging

from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.worker import Worker

from hamoon.app.config.settings import get_settings
from hamoon.domains.operations.domain.entities import (
    ReassessmentPlan,
    ReassessmentPlanStatus,
)
from hamoon.domains.operations.infrastructure.repositories import (
    SqlAlchemyReassessmentPlanRepository,
)
from hamoon.infrastructure.db.session import session_factory
from hamoon.infrastructure.temporal.activities import (
    generate_reassessment_outcome_ai,
    materialize_outcome_review_work_item,
    materialize_reassessment_work_item,
    prepare_reassessment_outcome,
)
from hamoon.infrastructure.temporal.reassessment_starter import (
    TemporalReassessmentStarter,
)
from hamoon.infrastructure.temporal.reassessment_workflow import (
    ReassessmentWorkflow,
)

logger = logging.getLogger(__name__)


async def _reconcile_active_plan(
    starter: TemporalReassessmentStarter,
    plan: ReassessmentPlan,
) -> None:
    await starter.start(plan)
    if plan.post_pgor_snapshot_id is not None:
        await starter.signal_post_pgor(plan)


async def _reconcile_completed_plan(
    starter: TemporalReassessmentStarter,
    plan: ReassessmentPlan,
) -> None:
    try:
        await starter.start(plan)
    except WorkflowAlreadyStartedError:
        # A successfully closed workflow must never be duplicated.
        return
    if plan.post_pgor_snapshot_id is not None:
        await starter.signal_post_pgor(plan)
    await starter.signal_outcome_reviewed(plan)


async def _reconcile(client: Client, task_queue: str) -> None:
    starter = TemporalReassessmentStarter(client=client, task_queue=task_queue)
    active_statuses = (
        ReassessmentPlanStatus.SCHEDULED,
        ReassessmentPlanStatus.TASK_CREATED,
        ReassessmentPlanStatus.REASSESSMENT_STARTED,
        ReassessmentPlanStatus.POST_PGOR_READY,
        ReassessmentPlanStatus.OUTCOME_REVIEW,
    )
    while True:
        try:
            async with session_factory() as session:
                repository = SqlAlchemyReassessmentPlanRepository(session)
                active = await repository.list_by_status(
                    statuses=active_statuses,
                    limit=200,
                )
                completed = await repository.list_by_status(
                    statuses=(ReassessmentPlanStatus.COMPLETED,),
                    limit=200,
                )
        except Exception:
            logger.exception("Temporal reconciliation database read failed")
            await asyncio.sleep(30)
            continue

        for plan in active:
            try:
                await _reconcile_active_plan(starter, plan)
            except Exception:
                logger.exception(
                    "Temporal reassessment reconciliation failed",
                    extra={"workflow_id": plan.workflow_id},
                )

        for plan in completed:
            try:
                await _reconcile_completed_plan(starter, plan)
            except Exception:
                logger.debug(
                    "Completed reassessment workflow not recoverable yet",
                    extra={"workflow_id": plan.workflow_id},
                    exc_info=True,
                )

        await asyncio.sleep(30)


async def run() -> None:
    settings = get_settings()
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
    )
    worker = Worker(
        client,
        task_queue=settings.temporal_core_task_queue,
        workflows=[ReassessmentWorkflow],
        activities=[
            materialize_reassessment_work_item,
            prepare_reassessment_outcome,
            generate_reassessment_outcome_ai,
            materialize_outcome_review_work_item,
        ],
    )
    await asyncio.gather(
        worker.run(),
        _reconcile(client, settings.temporal_core_task_queue),
    )


if __name__ == "__main__":
    asyncio.run(run())
