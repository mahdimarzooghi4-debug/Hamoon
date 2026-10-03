from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hamoon.domains.household.domain.entities import HouseholdStatus


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
