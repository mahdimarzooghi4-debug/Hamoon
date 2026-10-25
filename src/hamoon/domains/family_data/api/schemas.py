from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

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
    supersedes_fact_id: UUID | None = None
    expected_accepted_projection_version: int | None = Field(default=None, ge=1)
    correction_reason_code: str | None = Field(default=None, min_length=1, max_length=100)
    correction_reason_text: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def require_complete_correction(self) -> Self:
        fields = (
            self.expected_accepted_projection_version,
            self.correction_reason_code,
            self.correction_reason_text,
        )
        if self.supersedes_fact_id is None:
            if any(item is not None for item in fields):
                raise ValueError("Correction metadata requires supersedes_fact_id.")
        elif (
            any(item is None for item in fields)
            or not self.correction_reason_code
            or not self.correction_reason_code.strip()
            or not self.correction_reason_text
            or not self.correction_reason_text.strip()
        ):
            raise ValueError("Correction requires expected version and nonblank reason.")
        return self

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
    supersedes_fact_id: UUID | None
    correction_reason_code: str | None
    correction_reason_text: str | None


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


class AcceptedStateHistoryEntryData(BaseModel):
    id: UUID
    household_id: UUID
    fact_type: str
    previous_fact_id: UUID | None
    new_fact_id: UUID
    projection_version: int
    reason_code: str
    reason_text: str | None
    changed_by: UUID
    changed_at: datetime
    domain_event_id: UUID


class AcceptedStateHistoryResponse(BaseModel):
    data: list[AcceptedStateHistoryEntryData]
    next_before_version: int | None
    next_before_id: UUID | None


class AcceptedFactResponse(BaseModel):
    data: AcceptedFactData


class AcceptedStateResponse(BaseModel):
    data: list[AcceptedFactData]
