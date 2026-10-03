from typing import Protocol
from uuid import UUID

from hamoon.domains.provider.domain.entities import (
    Provider,
    ProviderCapacitySnapshot,
    ProviderEligibilityRule,
    ProviderMatch,
    ProviderMatchCandidate,
    ProviderSelection,
    ProviderService,
)


class ProviderRegistryRepository(Protocol):
    async def get_provider(self, provider_id: UUID) -> Provider | None: ...

    async def list_providers(self) -> list[Provider]: ...

    async def get_service(self, service_id: UUID) -> ProviderService | None: ...

    async def list_services_for_provider(
        self,
        provider_id: UUID,
    ) -> list[ProviderService]: ...

    async def list_services_by_type(
        self,
        service_type: str,
    ) -> list[ProviderService]: ...

    async def list_eligibility_rules(
        self,
        provider_service_id: UUID,
    ) -> list[ProviderEligibilityRule]: ...

    async def latest_capacity(
        self,
        provider_service_id: UUID,
    ) -> ProviderCapacitySnapshot | None: ...


class ProviderMatchRepository(Protocol):
    async def add(self, match: ProviderMatch) -> None: ...

    async def get(self, match_id: UUID) -> ProviderMatch | None: ...

    async def get_latest_for_intervention(
        self,
        intervention_id: UUID,
    ) -> ProviderMatch | None: ...

    async def get_candidate(
        self,
        *,
        provider_match_id: UUID,
        provider_id: UUID,
        provider_service_id: UUID,
    ) -> ProviderMatchCandidate | None: ...


class ProviderSelectionRepository(Protocol):
    async def add(self, selection: ProviderSelection) -> None: ...
