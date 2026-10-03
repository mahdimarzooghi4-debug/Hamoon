from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from hamoon.domains.intervention.domain.entities import (
    InterventionStatus,
    InterventionType,
)
from hamoon.domains.pgor.domain.definitions import PGORVariableCode


class InterventionData(BaseModel):
    id: UUID
    household_id: UUID
    prescription_item_id: UUID
    intervention_type: InterventionType
    target_pgor_variable: PGORVariableCode
    status: InterventionStatus
    started_at: datetime | None
    completed_at: datetime | None
    owner_actor_id: UUID | None


class InterventionResponse(BaseModel):
    data: InterventionData


class InterventionListResponse(BaseModel):
    data: list[InterventionData]
