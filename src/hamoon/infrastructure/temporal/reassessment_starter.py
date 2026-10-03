import logging

from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from hamoon.app.config.settings import Settings
from hamoon.domains.operations.domain.entities import ReassessmentPlan
from hamoon.infrastructure.temporal.contracts import (
    PostPGORReadySignal,
    ReassessmentWorkflowInput,
)
from hamoon.infrastructure.temporal.reassessment_workflow import ReassessmentWorkflow

logger = logging.getLogger(__name__)


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
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )

    async def signal_post_pgor(self, plan: ReassessmentPlan) -> None:
        if plan.post_assessment_id is None or plan.post_pgor_snapshot_id is None:
            raise ValueError("REASSESSMENT_POST_PGOR_NOT_READY")
        handle = self._client.get_workflow_handle(plan.workflow_id)
        await handle.signal(
            "PostPGORReady",
            PostPGORReadySignal(
                assessment_id=plan.post_assessment_id,
                snapshot_id=plan.post_pgor_snapshot_id,
            ),
        )

    async def signal_outcome_reviewed(self, plan: ReassessmentPlan) -> None:
        handle = self._client.get_workflow_handle(plan.workflow_id)
        await handle.signal("OutcomeReviewed")


async def start_reassessment_best_effort(
    *,
    plan: ReassessmentPlan,
    settings: Settings,
) -> bool:
    try:
        client = await Client.connect(
            settings.temporal_address,
            namespace=settings.temporal_namespace,
        )
        starter = TemporalReassessmentStarter(
            client=client,
            task_queue=settings.temporal_core_task_queue,
        )
        await starter.start(plan)
        return True
    except Exception:
        logger.exception(
            "Temporal reassessment start failed; reconciliation will retry",
            extra={"workflow_id": plan.workflow_id},
        )
        return False


async def signal_post_pgor_best_effort(
    *,
    plan: ReassessmentPlan,
    settings: Settings,
) -> bool:
    try:
        client = await Client.connect(
            settings.temporal_address,
            namespace=settings.temporal_namespace,
        )
        starter = TemporalReassessmentStarter(
            client=client,
            task_queue=settings.temporal_core_task_queue,
        )
        await starter.start(plan)
        await starter.signal_post_pgor(plan)
        return True
    except Exception:
        logger.exception(
            "Temporal post-PGOR signal failed; reconciliation will retry",
            extra={"workflow_id": plan.workflow_id},
        )
        return False


async def signal_outcome_reviewed_best_effort(
    *,
    plan: ReassessmentPlan,
    settings: Settings,
) -> bool:
    try:
        client = await Client.connect(
            settings.temporal_address,
            namespace=settings.temporal_namespace,
        )
        starter = TemporalReassessmentStarter(
            client=client,
            task_queue=settings.temporal_core_task_queue,
        )
        await starter.signal_outcome_reviewed(plan)
        return True
    except Exception:
        logger.exception(
            "Temporal outcome-reviewed signal failed; reconciliation will retry",
            extra={"workflow_id": plan.workflow_id},
        )
        return False
