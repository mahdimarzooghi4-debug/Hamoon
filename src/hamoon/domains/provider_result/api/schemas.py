from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, JsonValue


class SubmitProviderResultRequest(BaseModel):
    external_result_id: str = Field(min_length=1, max_length=250)
    result_status: str = Field(min_length=1, max_length=100)
    result_type: str = Field(min_length=1, max_length=150)
    result_summary: str = Field(min_length=1, max_length=4000)
    result_payload: dict[str, JsonValue] | None = None
    service_started_at: datetime | None = None
    service_completed_at: datetime | None = None
    evidence: list[UUID] = Field(default_factory=list)
    provider_reference: str | None = Field(default=None, max_length=500)


class ProviderResultData(BaseModel):
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
    evidence: list[UUID]
    duplicate: bool = False


class ProviderResultResponse(BaseModel):
    data: ProviderResultData


class ProviderResultListResponse(BaseModel):
    data: list[ProviderResultData]
