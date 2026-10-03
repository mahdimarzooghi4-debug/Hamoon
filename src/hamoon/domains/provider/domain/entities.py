from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from hamoon.domains.intervention.domain.entities import InterventionType


class ProviderStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class CapacityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    FULL = "FULL"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class EligibilityOperator(StrEnum):
    EXISTS = "EXISTS"
    EQUALS = "EQUALS"
    IN = "IN"


class MatchEligibility(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"


@dataclass(frozen=True, slots=True)
class Provider:
    id: UUID
    code: str
    name: str
    status: ProviderStatus
    organization_type: str | None
    integration_mode: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ProviderService:
    id: UUID
    provider_id: UUID
    service_type: str
    title: str
    description: str
    supported_intervention_types: tuple[InterventionType, ...]
    eligibility_policy_version: str | None
    coverage_policy_version: str | None
    coverage_fact_type: str | None
    coverage_codes: tuple[str, ...]
    sla_policy_version: str | None
    active: bool


@dataclass(frozen=True, slots=True)
class ProviderEligibilityRule:
    id: UUID
    provider_service_id: UUID
    fact_type: str
    operator: EligibilityOperator
    expected_value: object | None
    reason_code: str
    active: bool


@dataclass(frozen=True, slots=True)
class ProviderCapacitySnapshot:
    id: UUID
    provider_service_id: UUID
    capacity_status: CapacityStatus
    available_slots: int | None
    valid_at: datetime
    received_at: datetime
    source_reference: str | None


@dataclass(frozen=True, slots=True)
class ProviderMatchCandidate:
    id: UUID
    provider_match_id: UUID
    provider_id: UUID
    provider_service_id: UUID
    eligibility: MatchEligibility
    capacity_status: CapacityStatus
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProviderMatch:
    id: UUID
    household_id: UUID
    intervention_id: UUID
    service_type: str
    household_context_version: int
    matching_policy_version: str
    generated_at: datetime
    generated_by: UUID
    candidates: tuple[ProviderMatchCandidate, ...]


@dataclass(frozen=True, slots=True)
class ProviderSelection:
    id: UUID
    provider_match_id: UUID
    intervention_id: UUID
    provider_id: UUID
    provider_service_id: UUID
    human_decision_id: UUID
    selected_by: UUID
    selected_at: datetime



@dataclass(frozen=True, slots=True)
class ProviderIdentity:
    id: UUID
    provider_id: UUID
    actor_id: UUID
    issuer: str
    external_identity_subject: str
    created_at: datetime
