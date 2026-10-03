import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from hamoon.app.config.settings import get_settings
from hamoon.domains.operations.infrastructure.repositories import (
    SqlAlchemyReassessmentPlanRepository,
)
from hamoon.infrastructure.db.session import session_factory
from hamoon.infrastructure.temporal.activities import (
    materialize_reassessment_work_item,
)
from hamoon.infrastructure.temporal.reassessment_starter import (
    TemporalReassessmentStarter,
)
from hamoon.infrastructure.temporal.reassessment_workflow import (
    ReassessmentWorkflow,
)


async def _reconcile(client: Client, task_queue: str) -> None:
    starter = TemporalReassessmentStarter(client=client, task_queue=task_queue)
    while True:
        async with session_factory() as session:
            plans = await SqlAlchemyReassessmentPlanRepository(
                session
            ).list_scheduled(limit=200)
        for plan in plans:
            await starter.start(plan)
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
        activities=[materialize_reassessment_work_item],
    )
    await asyncio.gather(
        worker.run(),
        _reconcile(client, settings.temporal_core_task_queue),
    )


if __name__ == "__main__":
    asyncio.run(run())
