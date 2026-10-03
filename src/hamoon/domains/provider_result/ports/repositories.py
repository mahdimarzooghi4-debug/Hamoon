from typing import Protocol
from uuid import UUID

from hamoon.domains.provider_result.domain.entities import ProviderResult


class ProviderResultRepository(Protocol):
    async def add(self, result: ProviderResult) -> None: ...

    async def get(self, result_id: UUID) -> ProviderResult | None: ...

    async def get_by_external_result(
        self,
        *,
        provider_id: UUID,
        external_result_id: str,
    ) -> ProviderResult | None: ...

    async def list_for_referral(self, referral_id: UUID) -> list[ProviderResult]: ...
