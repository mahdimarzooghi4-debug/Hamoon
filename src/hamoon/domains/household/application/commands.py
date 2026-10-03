from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreateHouseholdCommand:
    case_code: str
    actor_id: UUID
    organizational_unit_id: str | None
    request_id: str
    correlation_id: str
