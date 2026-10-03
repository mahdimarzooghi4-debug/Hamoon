from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from hamoon.domains.family_data.domain.entities import (
    FactValidationStatus,
    FactValueType,
    SourceType,
)


class DataSourceData(BaseModel):
    id: UUID
    code: str
    source_type: SourceType
    name: str


class DataSourceListResponse(BaseModel):
    data: list[DataSourceData]


class RecordFactRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    fact_type: str = Field(min_length=1, max_length=150)
    value_type: FactValueType
    value: JsonValue
    source_id: UUID
    source_detail: str | None = Field(default=None, max_length=500)
    effective_from: datetime

    @field_validator("fact_type")
    @classmethod
    def normalize_fact_type(cls, value: str) -> str:
        return value.upper()


class FactData(BaseModel):
    id: UUID
    household_id: UUID
    fact_type: str
    value_type: FactValueType
    value: JsonValue
    source_id: UUID
    source_detail: str | None
    effective_from: datetime
    recorded_at: datetime
    version: int
    validation_status: FactValidationStatus
    validation_version: int


class FactResponse(BaseModel):
    data: FactData


class FactListResponse(BaseModel):
    data: list[FactData]


class ChangeValidationRequest(BaseModel):
    to_status: FactValidationStatus
    expected_validation_version: int = Field(ge=1)
    reason_code: str = Field(min_length=1, max_length=100)
    reason_text: str | None = Field(default=None, max_length=1000)


class ValidationData(BaseModel):
    fact_id: UUID
    status: FactValidationStatus
    version: int
    changed_at: datetime
    reason_code: str
    reason_text: str | None


class ValidationResponse(BaseModel):
    data: ValidationData


class ResolveAcceptedFactRequest(BaseModel):
    fact_id: UUID
    expected_projection_version: int = Field(default=0, ge=0)
    reason_code: str = Field(min_length=1, max_length=100)
    reason_text: str | None = Field(default=None, max_length=1000)


class AcceptedFactData(BaseModel):
    household_id: UUID
    fact_type: str
    fact_id: UUID
    accepted_value: JsonValue
    source_id: UUID
    effective_from: datetime
    projection_version: int
    projected_at: datetime


class AcceptedFactResponse(BaseModel):
    data: AcceptedFactData


class AcceptedStateResponse(BaseModel):
    data: list[AcceptedFactData]
