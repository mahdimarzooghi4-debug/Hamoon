from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from hamoon.domains.family_data.domain.entities import (
    FactValidationStatus,
    FactValueType,
)


@dataclass(frozen=True, slots=True)
class RecordHouseholdFactCommand:
    household_id: UUID
    actor_id: UUID
    fact_type: str
    value_type: FactValueType
    value: object
    source_id: UUID
    source_detail: str | None
    effective_from: datetime
    request_id: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ChangeFactValidationCommand:
    household_id: UUID
    fact_id: UUID
    actor_id: UUID
    to_status: FactValidationStatus
    expected_validation_version: int
    reason_code: str
    reason_text: str | None
    request_id: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ResolveAcceptedFactCommand:
    household_id: UUID
    fact_type: str
    fact_id: UUID
    actor_id: UUID
    expected_projection_version: int
    reason_code: str
    reason_text: str | None
    request_id: str
    correlation_id: str
