from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy

from hamoon.domains.operations.domain.entities import ReassessmentPlan
from hamoon.infrastructure.temporal.contracts import ReassessmentWorkflowInput
from hamoon.infrastructure.temporal.reassessment_workflow import ReassessmentWorkflow


class TemporalReassessmentStarter:
    def __init__(
        self,
        *,
        client: Client,
        task_queue: str,
    ) -> None:
        self._client = client
        self._task_queue = task_queue

    async def start(self, plan: ReassessmentPlan) -> None:
        await self._client.start_workflow(
            ReassessmentWorkflow.run,
            ReassessmentWorkflowInput(
                plan_id=plan.id,
                household_id=plan.household_id,
                due_at=plan.due_at,
                policy_version=plan.policy_version,
                actor_id=plan.created_by,
            ),
            id=plan.workflow_id,
            task_queue=self._task_queue,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )
