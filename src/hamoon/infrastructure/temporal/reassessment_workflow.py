from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from hamoon.infrastructure.temporal.contracts import (
    MaterializeReassessmentInput,
    ReassessmentWorkflowInput,
)


@workflow.defn(name="HamoonReassessmentWorkflow")
class ReassessmentWorkflow:
    def __init__(self) -> None:
        self._work_item_id: str | None = None
        self._completed = False

    @workflow.run
    async def run(self, data: ReassessmentWorkflowInput) -> str:
        delay = data.due_at - workflow.now()
        if delay.total_seconds() > 0:
            await workflow.sleep(delay)

        work_item_id = await workflow.execute_activity(
            "materialize_reassessment_work_item",
            MaterializeReassessmentInput(
                plan_id=data.plan_id,
                actor_id=data.actor_id,
                correlation_id=workflow.info().workflow_id,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=30),
                maximum_attempts=5,
            ),
            result_type=str,
        )
        self._work_item_id = work_item_id
        await workflow.wait_condition(lambda: self._completed)
        return work_item_id

    @workflow.signal(name="ReassessmentCompleted")
    async def reassessment_completed(self) -> None:
        self._completed = True

    @workflow.query(name="CurrentWorkItemId")
    def current_work_item_id(self) -> str | None:
        return self._work_item_id
