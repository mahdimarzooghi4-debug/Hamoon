from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID


class SourceType(StrEnum):
    HOUSEHOLD_DECLARATION = "HOUSEHOLD_DECLARATION"
    EXPERT_ASSESSMENT = "EXPERT_ASSESSMENT"
    EXTERNAL_DATA = "EXTERNAL_DATA"


class FactValueType(StrEnum):
    STRING = "STRING"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    DATETIME = "DATETIME"
    CODE = "CODE"
    RANGE = "RANGE"
    JSON_STRUCTURED = "JSON_STRUCTURED"


class FactValidationStatus(StrEnum):
    PENDING_VALIDATION = "PENDING_VALIDATION"
    VALIDATED = "VALIDATED"
    DISPUTED = "DISPUTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


_ALLOWED_VALIDATION_TRANSITIONS: dict[
    FactValidationStatus,
    frozenset[FactValidationStatus],
] = {
    FactValidationStatus.PENDING_VALIDATION: frozenset(
        {
            FactValidationStatus.VALIDATED,
            FactValidationStatus.DISPUTED,
            FactValidationStatus.REJECTED,
        }
    ),
    FactValidationStatus.VALIDATED: frozenset(
        {
            FactValidationStatus.DISPUTED,
            FactValidationStatus.SUPERSEDED,
        }
    ),
    FactValidationStatus.DISPUTED: frozenset(
        {
            FactValidationStatus.VALIDATED,
            FactValidationStatus.REJECTED,
            FactValidationStatus.SUPERSEDED,
        }
    ),
    FactValidationStatus.REJECTED: frozenset(),
    FactValidationStatus.SUPERSEDED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class DataSource:
    id: UUID
    code: str
    source_type: SourceType
    name: str
    active: bool


@dataclass(frozen=True, slots=True)
class HouseholdFact:
    id: UUID
    household_id: UUID
    fact_type: str
    value_type: FactValueType
    value: object
    source_id: UUID
    effective_from: datetime
    recorded_at: datetime
    recorded_by: UUID
    version: int = 1
    source_detail: str | None = None
    effective_to: datetime | None = None
    supersedes_fact_id: UUID | None = None
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class FactValidationState:
    fact_id: UUID
    status: FactValidationStatus
    version: int
    changed_at: datetime
    changed_by: UUID
    reason_code: str
    reason_text: str | None = None

    def transition(
        self,
        *,
        to_status: FactValidationStatus,
        changed_at: datetime,
        changed_by: UUID,
        reason_code: str,
        reason_text: str | None,
    ) -> "FactValidationState":
        allowed = _ALLOWED_VALIDATION_TRANSITIONS[self.status]
        if to_status not in allowed:
            from hamoon.domains.family_data.domain.errors import (
                InvalidValidationTransitionError,
            )

            raise InvalidValidationTransitionError(
                f"Cannot transition validation state from {self.status} to {to_status}."
            )

        return replace(
            self,
            status=to_status,
            version=self.version + 1,
            changed_at=changed_at,
            changed_by=changed_by,
            reason_code=reason_code,
            reason_text=reason_text,
        )


@dataclass(frozen=True, slots=True)
class CurrentAcceptedFact:
    household_id: UUID
    fact_type: str
    fact_id: UUID
    accepted_value: object
    source_id: UUID
    effective_from: datetime
    projection_version: int
    projected_at: datetime
    changed_by: UUID


def validate_fact_value(value_type: FactValueType, value: object) -> None:
    from hamoon.domains.family_data.domain.errors import InvalidFactValueError

    valid = False

    if value_type in {FactValueType.STRING, FactValueType.CODE}:
        valid = isinstance(value, str) and bool(value.strip())
    elif value_type is FactValueType.NUMBER:
        valid = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif value_type is FactValueType.BOOLEAN:
        valid = isinstance(value, bool)
    elif value_type is FactValueType.DATE:
        if isinstance(value, str):
            try:
                date.fromisoformat(value)
                valid = True
            except ValueError:
                valid = False
    elif value_type is FactValueType.DATETIME:
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                valid = parsed.tzinfo is not None
            except ValueError:
                valid = False
    elif value_type is FactValueType.RANGE:
        valid = isinstance(value, dict) and (
            "min" in value or "max" in value
        )
    elif value_type is FactValueType.JSON_STRUCTURED:
        valid = isinstance(value, (dict, list))

    if not valid:
        raise InvalidFactValueError(
            f"Value does not match declared value type {value_type}."
        )
