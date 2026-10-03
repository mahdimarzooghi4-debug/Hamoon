from datetime import datetime
from typing import Protocol
from uuid import UUID

from hamoon.domains.family_data.domain.entities import (
    CurrentAcceptedFact,
    DataSource,
    FactValidationState,
    FactValidationStatus,
    HouseholdFact,
)


class DataSourceRepository(Protocol):
    async def get(self, source_id: UUID) -> DataSource | None: ...

    async def list_active(self) -> list[DataSource]: ...


class HouseholdFactRepository(Protocol):
    async def add(self, fact: HouseholdFact) -> None: ...

    async def get_for_household(
        self,
        *,
        household_id: UUID,
        fact_id: UUID,
    ) -> HouseholdFact | None: ...

    async def list_for_household(self, household_id: UUID) -> list[HouseholdFact]: ...


class FactValidationRepository(Protocol):
    async def create_initial(
        self,
        *,
        state: FactValidationState,
        occurred_at: datetime,
    ) -> None: ...

    async def get_state(self, fact_id: UUID) -> FactValidationState | None: ...

    async def transition(
        self,
        *,
        previous: FactValidationState,
        current: FactValidationState,
    ) -> None: ...


class AcceptedStateRepository(Protocol):
    async def get(
        self,
        *,
        household_id: UUID,
        fact_type: str,
    ) -> CurrentAcceptedFact | None: ...

    async def list_for_household(
        self,
        household_id: UUID,
    ) -> list[CurrentAcceptedFact]: ...

    async def set_current(
        self,
        *,
        accepted: CurrentAcceptedFact,
        previous_fact_id: UUID | None,
        reason_code: str,
        reason_text: str | None,
        event_id: UUID,
    ) -> None: ...
