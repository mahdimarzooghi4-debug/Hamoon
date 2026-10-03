from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class HouseholdStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class CaseAssignmentType(StrEnum):
    PRIMARY = "PRIMARY"
    DELEGATED = "DELEGATED"


@dataclass(frozen=True, slots=True)
class Household:
    id: UUID
    case_code: str
    lifecycle_status: HouseholdStatus
    created_at: datetime
    created_by: UUID
    version: int = 1
    organizational_unit_id: str | None = None
    primary_caseworker_id: UUID | None = None
    closed_at: datetime | None = None

    def activate(self) -> "Household":
        if self.lifecycle_status is not HouseholdStatus.DRAFT:
            raise ValueError("Only a DRAFT household can be activated.")
        return replace(
            self,
            lifecycle_status=HouseholdStatus.ACTIVE,
            version=self.version + 1,
        )

    def close(self, *, closed_at: datetime) -> "Household":
        if self.lifecycle_status in {HouseholdStatus.CLOSED, HouseholdStatus.ARCHIVED}:
            raise ValueError("Household is already closed or archived.")
        return replace(
            self,
            lifecycle_status=HouseholdStatus.CLOSED,
            closed_at=closed_at,
            version=self.version + 1,
        )


@dataclass(frozen=True, slots=True)
class CaseAssignment:
    id: UUID
    household_id: UUID
    actor_id: UUID
    assignment_type: CaseAssignmentType
    valid_from: datetime
    assigned_by: UUID
    created_at: datetime
    valid_to: datetime | None = None
    reason: str | None = None

    def is_active_at(self, at: datetime) -> bool:
        if at < self.valid_from:
            return False
        return self.valid_to is None or at < self.valid_to
