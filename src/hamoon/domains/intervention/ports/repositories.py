from typing import Protocol
from uuid import UUID

from hamoon.domains.intervention.domain.entities import Intervention


class InterventionRepository(Protocol):
    async def add(self, intervention: Intervention) -> None: ...

    async def get(self, intervention_id: UUID) -> Intervention | None: ...

    async def get_by_prescription_item(
        self,
        prescription_item_id: UUID,
    ) -> Intervention | None: ...

    async def list_for_household(self, household_id: UUID) -> list[Intervention]: ...
