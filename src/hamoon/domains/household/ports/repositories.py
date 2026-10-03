from typing import Protocol
from uuid import UUID

from hamoon.domains.household.domain.entities import CaseAssignment, Household


class HouseholdRepository(Protocol):
    async def add(self, household: Household) -> None: ...

    async def get(self, household_id: UUID) -> Household | None: ...

    async def get_by_case_code(self, case_code: str) -> Household | None: ...


class CaseAssignmentRepository(Protocol):
    async def add(self, assignment: CaseAssignment) -> None: ...

    async def has_active_assignment(
        self,
        *,
        household_id: UUID,
        actor_id: UUID,
    ) -> bool: ...
