from typing import Protocol
from uuid import UUID

from hamoon.domains.prescription.domain.entities import Prescription, PrescriptionItem


class PrescriptionRepository(Protocol):
    async def add(self, prescription: Prescription) -> None: ...

    async def get(self, prescription_id: UUID) -> Prescription | None: ...

    async def update(
        self,
        prescription: Prescription,
        *,
        expected_version: int,
    ) -> None: ...

    async def add_items(self, items: tuple[PrescriptionItem, ...]) -> None: ...

    async def get_item(
        self,
        *,
        prescription_id: UUID,
        item_id: UUID,
    ) -> PrescriptionItem | None: ...

    async def get_item_by_id(self, item_id: UUID) -> PrescriptionItem | None: ...

    async def list_items(self, prescription_id: UUID) -> list[PrescriptionItem]: ...

    async def mark_item_activated(self, item_id: UUID) -> None: ...
