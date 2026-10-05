from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from hamoon.infrastructure.temporal.contracts import (
    DispatchReferralInput,
    MarkReferralNoResponseInput,
    ReferralStatusSignal,
    ReferralWorkflowInput,
)

_DISPATCH_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    maximum_interval=timedelta(seconds=30),
)

_ACTIVITY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(seconds=15),
    maximum_attempts=5,
)


@workflow.defn(name="HamoonReferralWorkflow")
class ReferralWorkflow:
    def __init__(self) -> None:
        self._provider_status: str | None = None
        self._cancelled = False

    @workflow.run
    async def run(self, data: ReferralWorkflowInput) -> str:
        await workflow.execute_activity(
            "dispatch_referral_to_provider",
            DispatchReferralInput(dispatch_id=data.dispatch_id),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_DISPATCH_RETRY,
            result_type=str,
        )

        if data.response_due_at is None:
            await workflow.wait_condition(
                lambda: self._provider_status is not None or self._cancelled
            )
        else:
            delay = data.response_due_at - workflow.now()
            if delay.total_seconds() > 0:
                try:
                    await workflow.wait_condition(
                        lambda: self._provider_status is not None or self._cancelled,
                        timeout=delay,
                    )
                except TimeoutError:
                    pass

        if self._cancelled:
            return "CANCELLED"
        if self._provider_status is not None:
            return self._provider_status

        return await workflow.execute_activity(
            "mark_referral_no_response",
            MarkReferralNoResponseInput(
                referral_id=data.referral_id,
                actor_id=data.actor_id,
                correlation_id=workflow.info().workflow_id,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_ACTIVITY_RETRY,
            result_type=str,
        )

    @workflow.signal(name="ProviderStatusReceived")
    async def provider_status_received(self, signal: ReferralStatusSignal) -> None:
        if self._provider_status is None:
            self._provider_status = signal.status

    @workflow.signal(name="ReferralCancelled")
    async def referral_cancelled(self) -> None:
        self._cancelled = True

    @workflow.query(name="ProviderStatus")
    def provider_status(self) -> str | None:
        return self._provider_status
