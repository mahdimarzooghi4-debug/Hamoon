from typing import Protocol
from uuid import UUID

from hamoon.domains.prescription.domain.entities import Prescription


class PrescriptionRepository(Protocol):
    async def add(self, prescription: Prescription) -> None: ...

    async def get(self, prescription_id: UUID) -> Prescription | None: ...
