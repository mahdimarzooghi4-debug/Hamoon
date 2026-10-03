from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import JsonValue


@dataclass(frozen=True, slots=True)
class SubmitProviderResultCommand:
    provider_id: UUID
    actor_id: UUID
    external_referral_id: str
    external_result_id: str
    result_status: str
    result_type: str
    result_summary: str
    result_payload: dict[str, JsonValue] | None
    service_started_at: datetime | None
    service_completed_at: datetime | None
    evidence_ids: tuple[UUID, ...]
    provider_reference: str | None
    correlation_id: str
