from __future__ import annotations

import logging
from uuid import UUID

from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from hamoon.app.config.settings import Settings
from hamoon.domains.referral.domain.entities import Referral, ReferralDispatch, ReferralStatus
from hamoon.infrastructure.temporal.contracts import (
    ReferralStatusSignal,
    ReferralWorkflowInput,
)
from hamoon.infrastructure.temporal.referral_workflow import ReferralWorkflow

logger = logging.getLogger(__name__)


def referral_workflow_id(*, referral_id: UUID, dispatch_id: UUID) -> str:
    return f"referral-{referral_id}-dispatch-{dispatch_id}"


class TemporalReferralStarter:
    def __init__(
        self,
        *,
        client: Client,
        task_queue: str,
    ) -> None:
        self._client = client
        self._task_queue = task_queue

    async def start(
        self,
        *,
        referral: Referral,
        dispatch: ReferralDispatch,
        actor_id: UUID,
    ) -> None:
        await self._client.start_workflow(
            ReferralWorkflow.run,
            ReferralWorkflowInput(
                referral_id=referral.id,
                dispatch_id=dispatch.id,
                response_due_at=referral.response_due_at,
                actor_id=actor_id,
            ),
            id=referral_workflow_id(
                referral_id=referral.id,
                dispatch_id=dispatch.id,
            ),
            task_queue=self._task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )

    async def signal_provider_status(
        self,
        *,
        referral_id: UUID,
        dispatch_id: UUID,
        status: ReferralStatus,
    ) -> None:
        handle = self._client.get_workflow_handle(
            referral_workflow_id(
                referral_id=referral_id,
                dispatch_id=dispatch_id,
            )
        )
        await handle.signal(
            "ProviderStatusReceived",
            ReferralStatusSignal(status=status.value),
        )

    async def signal_cancelled(
        self,
        *,
        referral_id: UUID,
        dispatch_id: UUID,
    ) -> None:
        handle = self._client.get_workflow_handle(
            referral_workflow_id(
                referral_id=referral_id,
                dispatch_id=dispatch_id,
            )
        )
        await handle.signal("ReferralCancelled")


async def _starter(settings: Settings) -> TemporalReferralStarter:
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
    )
    return TemporalReferralStarter(
        client=client,
        task_queue=settings.temporal_provider_task_queue,
    )


async def start_referral_workflow_best_effort(
    *,
    referral: Referral,
    dispatch: ReferralDispatch,
    actor_id: UUID,
    settings: Settings,
) -> bool:
    try:
        starter = await _starter(settings)
        await starter.start(
            referral=referral,
            dispatch=dispatch,
            actor_id=actor_id,
        )
        return True
    except Exception:
        logger.exception(
            "Temporal referral workflow start failed; provider worker reconciliation will retry",
            extra={
                "referral_id": str(referral.id),
                "dispatch_id": str(dispatch.id),
            },
        )
        return False


async def signal_referral_provider_status_best_effort(
    *,
    referral_id: UUID,
    dispatch_id: UUID,
    status: ReferralStatus,
    settings: Settings,
) -> bool:
    try:
        starter = await _starter(settings)
        await starter.signal_provider_status(
            referral_id=referral_id,
            dispatch_id=dispatch_id,
            status=status,
        )
        return True
    except Exception:
        logger.exception(
            "Temporal referral provider-status signal failed",
            extra={
                "referral_id": str(referral_id),
                "dispatch_id": str(dispatch_id),
                "status": status.value,
            },
        )
        return False


async def signal_referral_cancelled_best_effort(
    *,
    referral_id: UUID,
    dispatch_id: UUID,
    settings: Settings,
) -> bool:
    try:
        starter = await _starter(settings)
        await starter.signal_cancelled(
            referral_id=referral_id,
            dispatch_id=dispatch_id,
        )
        return True
    except Exception:
        logger.exception(
            "Temporal referral cancellation signal failed",
            extra={
                "referral_id": str(referral_id),
                "dispatch_id": str(dispatch_id),
            },
        )
        return False
