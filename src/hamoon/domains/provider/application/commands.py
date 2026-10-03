from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MatchProvidersCommand:
    intervention_id: UUID
    service_type: str
    household_context_version: int
    actor_id: UUID
    request_id: str
    correlation_id: str
