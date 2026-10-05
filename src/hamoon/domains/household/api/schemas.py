from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hamoon.domains.household.domain.entities import HouseholdStatus
from hamoon.domains.intervention.domain.entities import InterventionStatus, InterventionType
from hamoon.domains.operations.domain.entities import WorkItemStatus, WorkItemType
from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.pgor.domain.engine import EBand


class CreateHouseholdRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    case_code: str = Field(min_length=1, max_length=100)
    organizational_unit_id: str | None = Field(default=None, max_length=100)

    @field_validator("organizational_unit_id")
    @classmethod
    def empty_unit_to_none(cls, value: str | None) -> str | None:
        return value or None


class HouseholdData(BaseModel):
    id: UUID
    case_code: str
    lifecycle_status: HouseholdStatus
    organizational_unit_id: str | None
    primary_caseworker_id: UUID | None
    version: int


class ResponseMeta(BaseModel):
    request_id: str
    version: int


class CreateHouseholdResponse(BaseModel):
    data: HouseholdData
    meta: ResponseMeta


class HouseholdPGORData(BaseModel):
    snapshot_id: UUID
    assessment_id: UUID
    calculated_at: datetime
    p: Decimal
    g: Decimal
    o: Decimal
    r: Decimal
    e: Decimal
    e_band: EBand
    bottleneck_variables: list[PGORVariableCode]
    data_quality_flags: list[str]


class HouseholdInterventionData(BaseModel):
    id: UUID
    intervention_type: InterventionType
    target_pgor_variable: PGORVariableCode
    status: InterventionStatus


class HouseholdWorkItemData(BaseModel):
    id: UUID
    work_type: WorkItemType
    title: str
    reason: str
    priority: int
    status: WorkItemStatus
    due_at: datetime | None
    version: int


class HouseholdSummaryData(BaseModel):
    id: UUID
    case_code: str
    lifecycle_status: HouseholdStatus
    organizational_unit_id: str | None
    primary_caseworker_id: UUID | None
    version: int
    pgor: HouseholdPGORData | None
    current_intervention: HouseholdInterventionData | None
    next_work_item: HouseholdWorkItemData | None


class HouseholdTimelineItemData(BaseModel):
    kind: str
    entity_id: UUID
    occurred_at: datetime
    status: str
    detail: str | None = None


class HouseholdTimelineResponse(BaseModel):
    data: list[HouseholdTimelineItemData]


class HouseholdListResponse(BaseModel):
    data: list[HouseholdSummaryData]


class HouseholdDetailResponse(BaseModel):
    data: HouseholdSummaryData
