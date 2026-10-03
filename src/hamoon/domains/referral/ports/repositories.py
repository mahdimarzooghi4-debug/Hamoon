from datetime import datetime
from typing import Protocol
from uuid import UUID

from hamoon.domains.referral.domain.entities import (
    ProviderCallbackMessage,
    Referral,
    ReferralDispatch,
    ReferralEvent,
)


class ReferralRepository(Protocol):
    async def add(self, referral: Referral) -> None: ...

    async def get(self, referral_id: UUID) -> Referral | None: ...

    async def get_by_provider_reference(
        self,
        *,
        provider_id: UUID,
        external_referral_id: str,
    ) -> Referral | None: ...

    async def update(
        self,
        referral: Referral,
        *,
        expected_version: int,
    ) -> None: ...

    async def add_event(self, event: ReferralEvent) -> None: ...

    async def list_events(self, referral_id: UUID) -> list[ReferralEvent]: ...

    async def mark_data_items_shared(
        self,
        *,
        referral_id: UUID,
        shared_at: datetime,
        authorization_basis: str,
    ) -> None: ...


class ReferralDispatchRepository(Protocol):
    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> ReferralDispatch | None: ...

    async def add(self, dispatch: ReferralDispatch) -> None: ...


class ProviderCallbackInboxRepository(Protocol):
    async def get(
        self,
        *,
        provider_id: UUID,
        external_event_id: str,
    ) -> ProviderCallbackMessage | None: ...

    async def add(self, message: ProviderCallbackMessage) -> None: ...

    async def mark_processed(
        self,
        *,
        message_id: UUID,
        processed_at: datetime,
    ) -> None: ...
