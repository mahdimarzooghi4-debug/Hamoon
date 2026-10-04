from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from hamoon.domains.provider.domain.entities import (
    CapacityStatus,
    MatchEligibility,
    ProviderStatus,
)


class ProviderData(BaseModel):
    id: UUID
    code: str
    name: str
    status: ProviderStatus
    organization_type: str | None
    integration_mode: str
    created_at: datetime


class ProviderListResponse(BaseModel):
    data: list[ProviderData]


class ProviderResponse(BaseModel):
    data: ProviderData


class ProviderServiceData(BaseModel):
    id: UUID
    provider_id: UUID
    service_type: str
    title: str
    description: str
    supported_intervention_types: list[str]
    eligibility_policy_version: str | None
    coverage_policy_version: str | None
    coverage_fact_type: str | None
    coverage_codes: list[str]
    sla_policy_version: str | None
    active: bool
    capacity_status: CapacityStatus
    available_slots: int | None


class ProviderServiceListResponse(BaseModel):
    data: list[ProviderServiceData]


class ProviderServiceResponse(BaseModel):
    data: ProviderServiceData


class MatchProvidersRequest(BaseModel):
    service_type: str = Field(min_length=1, max_length=150)
    household_context_version: int = Field(ge=1)


class ProviderMatchCandidateData(BaseModel):
    provider_id: UUID
    provider_name: str
    provider_service_id: UUID
    service_title: str
    eligibility: MatchEligibility
    capacity_status: CapacityStatus
    reasons: list[str]


class ProviderMatchData(BaseModel):
    provider_match_id: UUID
    intervention_id: UUID
    ai_decision_id: UUID | None = None
    service_type: str
    household_context_version: int
    matching_policy_version: str
    generated_at: datetime
    candidates: list[ProviderMatchCandidateData]


class ProviderMatchResponse(BaseModel):
    data: ProviderMatchData


class ProviderMatchContextFactData(BaseModel):
    fact_id: UUID
    fact_type: str
    projection_version: int
    effective_from: datetime


class ProviderMatchServiceTypeData(BaseModel):
    service_type: str
    service_titles: list[str]
    active_service_count: int


class ProviderMatchContextData(BaseModel):
    intervention_id: UUID
    intervention_type: str
    target_pgor_variable: str
    household_context_version: int
    service_types: list[ProviderMatchServiceTypeData]
    shareable_facts: list[ProviderMatchContextFactData]


class ProviderMatchContextResponse(BaseModel):
    data: ProviderMatchContextData
