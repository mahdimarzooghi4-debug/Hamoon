from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import JsonValue


@dataclass(frozen=True, slots=True)
class ProviderResult:
    id: UUID
    referral_id: UUID
    provider_id: UUID
    result_status: str
    result_type: str
    result_summary: str
    result_payload: dict[str, JsonValue] | None
    service_started_at: datetime | None
    service_completed_at: datetime | None
    submitted_at: datetime
    external_result_id: str
    provider_reference: str | None
    request_hash: str
    evidence_ids: tuple[UUID, ...] = ()
