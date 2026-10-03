from datetime import UTC, datetime
from uuid import UUID

import pytest
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from hamoon.domains.operations.domain.entities import (
    ReassessmentPlan,
    ReassessmentPlanStatus,
)
from hamoon.infrastructure.temporal.reassessment_starter import (
    TemporalReassessmentStarter,
)
from hamoon.infrastructure.temporal.worker import (
    _reconcile_active_plan,
    _reconcile_completed_plan,
)

ACTOR = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD = UUID("22222222-2222-2222-2222-222222222222")
INTERVENTION = UUID("33333333-3333-3333-3333-333333333333")
PROVIDER_RESULT = UUID("44444444-4444-4444-4444-444444444444")
PRESCRIPTION_ITEM = UUID("55555555-5555-5555-5555-555555555555")
ASSESSMENT = UUID("66666666-6666-6666-6666-666666666666")
SNAPSHOT = UUID("77777777-7777-7777-7777-777777777777")
OUTCOME = UUID("88888888-8888-8888-8888-888888888888")
OUTCOME_WORK_ITEM = UUID("99999999-9999-9999-9999-999999999999")


def _plan(status: ReassessmentPlanStatus) -> ReassessmentPlan:
    return ReassessmentPlan(
        id=PROVIDER_RESULT,
        household_id=HOUSEHOLD,
        intervention_id=INTERVENTION,
        provider_result_id=PROVIDER_RESULT,
        prescription_item_id=PRESCRIPTION_ITEM,
        assigned_actor_id=ACTOR,
        review_after_days=14,
        due_at=datetime(2026, 1, 1, tzinfo=UTC),
        policy_version="prescription-item-review-v1",
        workflow_id=f"reassessment:{PROVIDER_RESULT}",
        status=status,
        version=6,
        created_at=datetime(2025, 12, 1, tzinfo=UTC),
        created_by=ACTOR,
        work_item_id=PRESCRIPTION_ITEM,
        task_created_at=datetime(2026, 1, 1, tzinfo=UTC),
        post_assessment_id=ASSESSMENT,
        post_pgor_snapshot_id=SNAPSHOT,
        outcome_id=OUTCOME,
        outcome_work_item_id=OUTCOME_WORK_ITEM,
    )


class _Starter:
    def __init__(self, *, already_closed: bool = False) -> None:
        self.calls: list[str] = []
        self.already_closed = already_closed

    async def start(self, plan: ReassessmentPlan) -> None:
        self.calls.append(f"start:{plan.workflow_id}")
        if self.already_closed:
            raise WorkflowAlreadyStartedError(
                plan.workflow_id,
                "HamoonReassessmentWorkflow",
            )

    async def signal_post_pgor(self, plan: ReassessmentPlan) -> None:
        self.calls.append(f"post-pgor:{plan.post_pgor_snapshot_id}")

    async def signal_outcome_reviewed(self, plan: ReassessmentPlan) -> None:
        self.calls.append(f"outcome-reviewed:{plan.outcome_id}")


class _Client:
    def __init__(self) -> None:
        self.kwargs = None

    async def start_workflow(self, *_args, **kwargs):
        self.kwargs = kwargs
        return object()


@pytest.mark.asyncio
async def test_starter_prevents_duplicate_successful_workflow_runs() -> None:
    client = _Client()
    starter = TemporalReassessmentStarter(
        client=client,
        task_queue="hamoon-core",
    )

    await starter.start(_plan(ReassessmentPlanStatus.COMPLETED))

    assert client.kwargs is not None
    assert (
        client.kwargs["id_reuse_policy"]
        is WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY
    )
    assert (
        client.kwargs["id_conflict_policy"]
        is WorkflowIDConflictPolicy.USE_EXISTING
    )


@pytest.mark.asyncio
async def test_active_reconciliation_restarts_and_replays_post_pgor() -> None:
    starter = _Starter()

    await _reconcile_active_plan(
        starter,
        _plan(ReassessmentPlanStatus.POST_PGOR_READY),
    )

    assert starter.calls == [
        f"start:reassessment:{PROVIDER_RESULT}",
        f"post-pgor:{SNAPSHOT}",
    ]


@pytest.mark.asyncio
async def test_completed_reconciliation_recovers_full_temporal_state() -> None:
    starter = _Starter()

    await _reconcile_completed_plan(
        starter,
        _plan(ReassessmentPlanStatus.COMPLETED),
    )

    assert starter.calls == [
        f"start:reassessment:{PROVIDER_RESULT}",
        f"post-pgor:{SNAPSHOT}",
        f"outcome-reviewed:{OUTCOME}",
    ]


@pytest.mark.asyncio
async def test_completed_reconciliation_does_not_duplicate_closed_success() -> None:
    starter = _Starter(already_closed=True)

    await _reconcile_completed_plan(
        starter,
        _plan(ReassessmentPlanStatus.COMPLETED),
    )

    assert starter.calls == [f"start:reassessment:{PROVIDER_RESULT}"]
