from datetime import timedelta
from uuid import UUID

from temporalio import workflow
from temporalio.common import RetryPolicy

from hamoon.infrastructure.temporal.contracts import (
    GenerateOutcomeAIInput,
    MaterializeOutcomeReviewInput,
    MaterializeReassessmentInput,
    PostPGORReadySignal,
    PrepareOutcomeInput,
    ReassessmentWorkflowInput,
)


_ACTIVITY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=5,
)


@workflow.defn(name="HamoonReassessmentWorkflow")
class ReassessmentWorkflow:
    def __init__(self) -> None:
        self._reassessment_work_item_id: str | None = None
        self._post_pgor: PostPGORReadySignal | None = None
        self._outcome_id: str | None = None
        self._outcome_review_work_item_id: str | None = None
        self._outcome_reviewed = False

    @workflow.run
    async def run(self, data: ReassessmentWorkflowInput) -> str:
        delay = data.due_at - workflow.now()
        if delay.total_seconds() > 0:
            await workflow.sleep(delay)

        self._reassessment_work_item_id = await workflow.execute_activity(
            "materialize_reassessment_work_item",
            MaterializeReassessmentInput(
                plan_id=data.plan_id,
                actor_id=data.actor_id,
                correlation_id=workflow.info().workflow_id,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_ACTIVITY_RETRY,
            result_type=str,
        )

        await workflow.wait_condition(lambda: self._post_pgor is not None)
        post_pgor = self._post_pgor
        if post_pgor is None:
            raise RuntimeError("POST_PGOR_SIGNAL_MISSING")

        self._outcome_id = await workflow.execute_activity(
            "prepare_reassessment_outcome",
            PrepareOutcomeInput(
                plan_id=data.plan_id,
                post_assessment_id=post_pgor.assessment_id,
                post_snapshot_id=post_pgor.snapshot_id,
                actor_id=data.actor_id,
                correlation_id=workflow.info().workflow_id,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_ACTIVITY_RETRY,
            result_type=str,
        )

        outcome_id = UUID(self._outcome_id)
        await workflow.execute_activity(
            "generate_reassessment_outcome_ai",
            GenerateOutcomeAIInput(
                outcome_id=outcome_id,
                actor_id=data.actor_id,
                correlation_id=workflow.info().workflow_id,
            ),
            start_to_close_timeout=timedelta(seconds=90),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                maximum_interval=timedelta(seconds=30),
                maximum_attempts=3,
            ),
            result_type=str,
        )

        self._outcome_review_work_item_id = await workflow.execute_activity(
            "materialize_outcome_review_work_item",
            MaterializeOutcomeReviewInput(
                plan_id=data.plan_id,
                outcome_id=outcome_id,
                actor_id=data.actor_id,
                correlation_id=workflow.info().workflow_id,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_ACTIVITY_RETRY,
            result_type=str,
        )

        await workflow.wait_condition(lambda: self._outcome_reviewed)
        return self._outcome_id

    @workflow.signal(name="PostPGORReady")
    async def post_pgor_ready(self, signal: PostPGORReadySignal) -> None:
        if self._post_pgor is None:
            self._post_pgor = signal
            return
        if self._post_pgor != signal:
            raise ValueError("POST_PGOR_SIGNAL_CONFLICT")

    @workflow.signal(name="OutcomeReviewed")
    async def outcome_reviewed(self) -> None:
        self._outcome_reviewed = True

    @workflow.query(name="CurrentReassessmentWorkItemId")
    def current_reassessment_work_item_id(self) -> str | None:
        return self._reassessment_work_item_id

    @workflow.query(name="CurrentOutcomeId")
    def current_outcome_id(self) -> str | None:
        return self._outcome_id

    @workflow.query(name="CurrentOutcomeReviewWorkItemId")
    def current_outcome_review_work_item_id(self) -> str | None:
        return self._outcome_review_work_item_id
