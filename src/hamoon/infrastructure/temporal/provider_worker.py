from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from hamoon.app.config.settings import Settings, get_settings
from hamoon.app.observability.heartbeats import record_worker_heartbeat_safe
from hamoon.domains.referral.domain.entities import (
    Referral,
    ReferralDispatch,
    ReferralStatus,
)
from hamoon.domains.referral.infrastructure.repositories import (
    SqlAlchemyReferralDispatchRepository,
    SqlAlchemyReferralRepository,
)
from hamoon.infrastructure.db.session import session_factory
from hamoon.infrastructure.provider_dispatch import load_provider_dispatch_targets
from hamoon.infrastructure.temporal.referral_activities import (
    dispatch_referral_to_provider,
    mark_referral_no_response,
)
from hamoon.infrastructure.temporal.referral_starter import TemporalReferralStarter
from hamoon.infrastructure.temporal.referral_workflow import ReferralWorkflow

logger = logging.getLogger(__name__)


async def _reconcile(
    client: Client,
    task_queue: str,
) -> None:
    starter = TemporalReferralStarter(
        client=client,
        task_queue=task_queue,
    )
    while True:
        try:
            async with session_factory() as session:
                dispatches = await SqlAlchemyReferralDispatchRepository(
                    session
                ).list_pending(limit=200)
                referrals = SqlAlchemyReferralRepository(session)
                pending: list[tuple[Referral, ReferralDispatch]] = []
                for dispatch in dispatches:
                    referral = await referrals.get(dispatch.referral_id)
                    if referral is None or referral.status is not ReferralStatus.SENT:
                        continue
                    pending.append((referral, dispatch))
        except Exception:
            logger.exception("Provider workflow reconciliation database read failed")
            await asyncio.sleep(30)
            continue

        for referral, dispatch in pending:
            try:
                await starter.start(
                    referral=referral,
                    dispatch=dispatch,
                    actor_id=referral.created_by,
                )
            except Exception:
                logger.exception(
                    "Provider workflow reconciliation failed",
                    extra={
                        "referral_id": str(referral.id),
                        "dispatch_id": str(dispatch.id),
                    },
                )
        await asyncio.sleep(30)


async def _heartbeat_loop(settings: Settings) -> None:
    while True:
        await record_worker_heartbeat_safe(
            worker_name="provider-worker",
            settings=settings,
        )
        await asyncio.sleep(15)


async def run() -> None:
    settings = get_settings()
    if settings.environment.strip().lower() in {"prod", "production"}:
        load_provider_dispatch_targets(settings)

    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
    )
    worker = Worker(
        client,
        task_queue=settings.temporal_provider_task_queue,
        workflows=[ReferralWorkflow],
        activities=[
            dispatch_referral_to_provider,
            mark_referral_no_response,
        ],
    )
    await asyncio.gather(
        worker.run(),
        _reconcile(client, settings.temporal_provider_task_queue),
        _heartbeat_loop(settings),
    )


if __name__ == "__main__":
    asyncio.run(run())
