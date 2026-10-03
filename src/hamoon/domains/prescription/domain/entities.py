from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import JsonValue


class PrescriptionStatus(StrEnum):
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    MODIFIED = "MODIFIED"
    REPLACED = "REPLACED"
    DEFERRED = "DEFERRED"


@dataclass(frozen=True, slots=True)
class Prescription:
    id: UUID
    household_id: UUID
    diagnosis_id: UUID
    ai_decision_id: UUID
    pgor_snapshot_id: UUID
    status: PrescriptionStatus
    version: int
    accepted_payload: dict[str, JsonValue] | None
    created_at: datetime
    created_by: UUID
