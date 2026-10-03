from datetime import UTC, datetime
from uuid import UUID

import pytest

from hamoon.domains.provider_result.application.commands import SubmitProviderResultCommand
from hamoon.domains.provider_result.application.handlers import SubmitProviderResultHandler
from hamoon.domains.provider_result.domain.errors import ProviderResultIdempotencyConflictError
from hamoon.domains.referral.domain.entities import Referral, ReferralStatus

ACTOR=UUID("11111111-1111-1111-1111-111111111111")
PROVIDER=UUID("22222222-2222-2222-2222-222222222222")
REF=UUID("33333333-3333-3333-3333-333333333333")


class Referrals:
    async def get_by_provider_reference(self,*,provider_id,external_referral_id):
        if provider_id != PROVIDER or external_referral_id != "ext-ref": return None
        return Referral(REF,UUID("44444444-4444-4444-4444-444444444444"),UUID("55555555-5555-5555-5555-555555555555"),UUID("66666666-6666-6666-6666-666666666666"),UUID("77777777-7777-7777-7777-777777777777"),PROVIDER,UUID("88888888-8888-8888-8888-888888888888"),ReferralStatus.IN_PROGRESS,"NORMAL",3,None,datetime.now(UTC),datetime.now(UTC),None,None,"ext-ref","subject",ACTOR,datetime.now(UTC),())
    async def get(self,item_id): return None
    async def add(self,item): pass
    async def update(self,*args,**kwargs): pass
    async def add_event(self,item): pass
    async def list_events(self,item_id): return []
    async def mark_data_items_shared(self,**kwargs): pass


class Results:
    def __init__(self): self.item=None
    async def add(self,item): self.item=item
    async def get(self,item_id): return self.item if self.item and self.item.id == item_id else None
    async def get_by_external_result(self,*,provider_id,external_result_id):
        if self.item and self.item.provider_id == provider_id and self.item.external_result_id == external_result_id: return self.item
        return None
    async def list_for_referral(self,item_id): return []


class Recorder:
    def __init__(self): self.items=[]
    async def record(self,item): self.items.append(item)


@pytest.mark.asyncio
async def test_provider_result_is_idempotent_and_not_hamoon_outcome() -> None:
    results=Results()
    events=Recorder()
    handler=SubmitProviderResultHandler(referrals=Referrals(),results=results,events=events,audits=Recorder())
    command=SubmitProviderResultCommand(
        provider_id=PROVIDER,
        actor_id=ACTOR,
        external_referral_id="ext-ref",
        external_result_id="result-1",
        result_status="COMPLETED",
        result_type="SERVICE_COMPLETION",
        result_summary="Service completed.",
        result_payload={"provider_metric":"ok"},
        service_started_at=None,
        service_completed_at=datetime.now(UTC),
        evidence_ids=(),
        provider_reference=None,
        correlation_id="corr",
    )
    first=await handler.handle(command)
    second=await handler.handle(command)
    assert first.duplicate is False
    assert second.duplicate is True
    assert first.result.referral_id == REF
    assert events.items[0].event_type == "ProviderResultReceived"

    changed=SubmitProviderResultCommand(
        provider_id=PROVIDER,
        actor_id=ACTOR,
        external_referral_id="ext-ref",
        external_result_id="result-1",
        result_status="FAILED",
        result_type="SERVICE_COMPLETION",
        result_summary="Different result.",
        result_payload=None,
        service_started_at=None,
        service_completed_at=command.service_completed_at,
        evidence_ids=(),
        provider_reference=None,
        correlation_id="corr",
    )
    with pytest.raises(ProviderResultIdempotencyConflictError):
        await handler.handle(changed)
