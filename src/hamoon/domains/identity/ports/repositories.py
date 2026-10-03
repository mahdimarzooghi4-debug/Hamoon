from datetime import datetime
from typing import Protocol

from hamoon.domains.identity.domain.entities import Actor


class IdentityRepository(Protocol):
    async def resolve_or_provision_human(
        self,
        *,
        issuer: str,
        subject: str,
        display_name: str | None,
        now: datetime,
    ) -> Actor: ...
