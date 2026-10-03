from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from hamoon.domains.pgor.domain.definitions import PGORVariableCode


class InterventionType(StrEnum):
    COUNSELING = "COUNSELING"
    MOTIVATION = "MOTIVATION"
    PSYCHOLOGICAL_EMPOWERMENT = "PSYCHOLOGICAL_EMPOWERMENT"
    COACHING = "COACHING"
    TRAINING = "TRAINING"
    SKILLS_TRAINING = "SKILLS_TRAINING"
    VOCATIONAL_TRAINING = "VOCATIONAL_TRAINING"
    MARKET_LINKAGE = "MARKET_LINKAGE"
    EMPLOYMENT = "EMPLOYMENT"
    FINANCING_FACILITIES = "FINANCING_FACILITIES"
    NETWORKING = "NETWORKING"
    SOCIAL_SUPPORT = "SOCIAL_SUPPORT"
    TREATMENT = "TREATMENT"
    RISK_REDUCTION = "RISK_REDUCTION"
    STABILIZATION = "STABILIZATION"


class InterventionStatus(StrEnum):
    PLANNED = "PLANNED"
    READY_FOR_REFERRAL = "READY_FOR_REFERRAL"
    REFERRED = "REFERRED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class Intervention:
    id: UUID
    household_id: UUID
    prescription_item_id: UUID
    intervention_type: InterventionType
    target_pgor_variable: PGORVariableCode
    status: InterventionStatus
    started_at: datetime | None
    completed_at: datetime | None
    owner_actor_id: UUID | None
