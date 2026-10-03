from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SharedFactInput:
    source_fact_id: UUID
    purpose: str


@dataclass(frozen=True, slots=True)
class CreateReferralCommand:
    intervention_id: UUID
    provider_id: UUID
    provider_service_id: UUID
    priority: str
    response_due_at: datetime | None
    shared_data_items: tuple[SharedFactInput, ...]
    actor_id: UUID
    request_id: str
    correlation_id: str
