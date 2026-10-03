from dataclasses import dataclass
from uuid import UUID

from pydantic import JsonValue

from hamoon.domains.intelligence.domain.decisions import HumanDecisionAction


@dataclass(frozen=True, slots=True)
class GenerateDiagnosisCommand:
    household_id: UUID
    pgor_snapshot_id: UUID
    actor_id: UUID
    request_id: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ReviewDiagnosisCommand:
    diagnosis_id: UUID
    actor_id: UUID
    action: HumanDecisionAction
    expected_version: int
    reason_code: str | None
    reason_text: str | None
    modified_payload: dict[str, JsonValue] | None
    request_id: str
    correlation_id: str
