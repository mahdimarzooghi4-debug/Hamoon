from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class GeneratePrescriptionCommand:
    household_id: UUID
    diagnosis_id: UUID
    pgor_snapshot_id: UUID
    actor_id: UUID
    request_id: str
    correlation_id: str
