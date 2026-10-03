from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ActivateInterventionCommand:
    prescription_id: UUID
    prescription_item_id: UUID
    actor_id: UUID
    request_id: str
    correlation_id: str
