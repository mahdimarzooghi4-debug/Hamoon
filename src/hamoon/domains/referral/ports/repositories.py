from typing import Protocol
from uuid import UUID

from hamoon.domains.referral.domain.entities import Referral


class ReferralRepository(Protocol):
    async def add(self, referral: Referral) -> None: ...

    async def get(self, referral_id: UUID) -> Referral | None: ...
