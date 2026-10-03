from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CalculateOfficialPGORCommand:
    assessment_id: UUID
    formula_version_id: UUID
    actor_id: UUID
    request_id: str
    correlation_id: str
