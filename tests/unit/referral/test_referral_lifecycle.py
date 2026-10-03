from datetime import UTC, datetime
from uuid import UUID

import pytest

from hamoon.domains.provider.domain.entities import (
    ProviderService,
)
from hamoon.domains.intervention.domain.entities import InterventionType
from hamoon.domains.referral.application.commands import (
    ProviderStatusCallbackCommand,
    SendReferralCommand,
)
from hamoon.domains.referral.application.lifecycle import (
    ProviderStatusCallbackHandler,
    SendReferralHandler,
)
from hamoon.domains.referral.domain.entities import (
    ProviderCallbackMessage,
    Referral,
    ReferralDataItem,
    ReferralDispatch,
    ReferralEvent,
    ReferralStatus,
)
from hamoon.domains.referral.domain.errors import ReferralIdempotencyConflictError

ACTOR=UUID("11111111-1111-1111-1111-111111111111")
PROVIDER=UUID("22222222-2222-2222-2222-222222222222")
SERVICE=UUID("33333333-3333-3333-3333-333333333333")
REFERRAL=UUID("44444444-4444-4444-4444-444444444444")
HH=UUID("55555555-5555-5555-5555-555555555555")


def make_referral() -> Referral:
    return Referral(
        id=REFERRAL,
        household_id=HH,
        intervention_id=UUID("66666666-6666-6666-6666-666666666666"),
        provider_match_id=UUID("77777777-7777-7777-7777-777777777777"),
        provider_selection_id=UUID("88888888-8888-8888-8888-888888888888"),
        provider_id=PROVIDER,
        provider_service_id=SERVICE,
        status=ReferralStatus.READY,
        priority="NORMAL",
        version=1,
        response_due_at=None,
        sent_at=None,
        accepted_at=None,
        completed_at=None,
        cancelled_at=None,
        external_referral_id=None,
        subject_reference=None,
        created_by=ACTOR,
        created_at=datetime.now(UTC),
        data_items=(
            ReferralDataItem(
                id=UUID("99999999-9999-9999-9999-999999999999"),
                referral_id=REFERRAL,
                data_category="geo.coverage_code",
                source_fact_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                snapshot_value="TEHRAN-1",
                purpose="SERVICE_ELIGIBILITY",
                authorization_basis=None,
                shared_at=None,
            ),
        ),
    )


class ReferralRepo:
    def __init__(self):
        self.item=make_referral()
        self.events:list[ReferralEvent]=[]
    async def add(self,item): self.item=item
    async def get(self,referral_id): return self.item if referral_id == REFERRAL else None
    async def get_by_provider_reference(self, *, provider_id, external_referral_id):
        if provider_id == PROVIDER and self.item.external_referral_id == external_referral_id:
            return self.item
        return None
    async def update(self,item,*,expected_version):
        assert self.item.version == expected_version
        self.item=item
    async def add_event(self,event): self.events.append(event)
    async def list_events(self,referral_id): return self.events
    async def mark_data_items_shared(self, *, referral_id, shared_at, authorization_basis):
        from dataclasses import replace
        self.item=replace(
            self.item,
            data_items=tuple(
                replace(x,shared_at=shared_at,authorization_basis=authorization_basis)
                for x in self.item.data_items
            ),
        )


class DispatchRepo:
    def __init__(self): self.item:ReferralDispatch|None=None
    async def get_by_idempotency_key(self,key):
        return self.item if self.item and self.item.idempotency_key == key else None
    async def add(self,item): self.item=item


class Registry:
    async def get_service(self,service_id):
        if service_id != SERVICE:
            return None
        return ProviderService(
            id=SERVICE,
            provider_id=PROVIDER,
            service_type="EMPLOYMENT_MARKET",
            title="Market linkage",
            description="",
            supported_intervention_types=(InterventionType.MARKET_LINKAGE,),
            eligibility_policy_version=None,
            coverage_policy_version=None,
            coverage_fact_type=None,
            coverage_codes=(),
            sla_policy_version=None,
            active=True,
        )
    async def resolve_identity(self,*,issuer,subject): return None
    async def get_provider(self,provider_id): return None
    async def list_providers(self): return []
    async def list_services_for_provider(self,provider_id): return []
    async def list_services_by_type(self,service_type): return []
    async def list_eligibility_rules(self,provider_service_id): return []
    async def latest_capacity(self,provider_service_id): return None


class Inbox:
    def __init__(self): self.items:dict[str,ProviderCallbackMessage]={}
    async def get(self,*,provider_id,external_event_id):
        return self.items.get(external_event_id)
    async def add(self,item): self.items[item.external_event_id]=item
    async def mark_processed(self,*,message_id,processed_at): return None


class Recorder:
    def __init__(self): self.items=[]
    async def record(self,item): self.items.append(item)


@pytest.mark.asyncio
async def test_send_is_idempotent_and_marks_only_explicit_data_shared() -> None:
    referrals=ReferralRepo()
    dispatches=DispatchRepo()
    events=Recorder()
    handler=SendReferralHandler(
        referrals=referrals,
        dispatches=dispatches,
        registry=Registry(),
        events=events,
        audits=Recorder(),
    )
    command=SendReferralCommand(
        referral_id=REFERRAL,
        expected_version=1,
        idempotency_key="send-1",
        actor_id=ACTOR,
        request_id="req",
        correlation_id="corr",
    )
    first=await handler.handle(command)
    second=await handler.handle(command)
    assert first.referral.status is ReferralStatus.SENT
    assert first.referral.version == 2
    assert first.dispatch.payload["authorized_data"] == {"geo.coverage_code":["TEHRAN-1"]}
    assert referrals.item.data_items[0].authorization_basis == "CASEWORKER_REFERRAL_SEND"
    assert second.replayed is True
    assert len(events.items) == 2


@pytest.mark.asyncio
async def test_provider_callback_is_idempotent_and_scoped() -> None:
    referrals=ReferralRepo()
    dispatch=DispatchRepo()
    await SendReferralHandler(
        referrals=referrals,
        dispatches=dispatch,
        registry=Registry(),
        events=Recorder(),
        audits=Recorder(),
    ).handle(
        SendReferralCommand(
            referral_id=REFERRAL,
            expected_version=1,
            idempotency_key="send-2",
            actor_id=ACTOR,
            request_id="req",
            correlation_id="corr",
        )
    )
    inbox=Inbox()
    handler=ProviderStatusCallbackHandler(
        referrals=referrals,
        inbox=inbox,
        events=Recorder(),
        audits=Recorder(),
    )
    ref=referrals.item.external_referral_id
    assert ref is not None
    command=ProviderStatusCallbackCommand(
        provider_id=PROVIDER,
        actor_id=ACTOR,
        external_referral_id=ref,
        external_event_id="evt-1",
        to_status=ReferralStatus.ACCEPTED,
        occurred_at=datetime.now(UTC),
        reason_code=None,
        schema_version="1",
        correlation_id="corr",
    )
    first=await handler.handle(command)
    second=await handler.handle(command)
    assert first.referral.status is ReferralStatus.ACCEPTED
    assert second.duplicate is True

    conflict=ProviderStatusCallbackCommand(
        provider_id=PROVIDER,
        actor_id=ACTOR,
        external_referral_id=ref,
        external_event_id="evt-1",
        to_status=ReferralStatus.REJECTED,
        occurred_at=command.occurred_at,
        reason_code=None,
        schema_version="1",
        correlation_id="corr",
    )
    with pytest.raises(
        ReferralIdempotencyConflictError,
        match="EXTERNAL_EVENT_REUSED_WITH_DIFFERENT_PAYLOAD",
    ):
        await handler.handle(conflict)


def test_referral_state_machine_rejects_invalid_transition() -> None:
    referral=make_referral()
    with pytest.raises(ValueError, match="Invalid referral transition"):
        referral.transition(
            to_status=ReferralStatus.COMPLETED,
            occurred_at=datetime.now(UTC),
        )
