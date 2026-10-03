from uuid import UUID

from pydantic import BaseModel

from hamoon.domains.pgor.domain.definitions import (
    PGORDefinitionStatus,
    PGORVariableCode,
    RequirementPolicyStatus,
)


class IndicatorDefinitionData(BaseModel):
    id: UUID
    dimension_definition_id: UUID
    code: str
    name_fa: str
    score_min: int
    score_max: int
    required_for_complete_assessment: bool | None
    direct_dimension_measure: bool
    sort_order: int


class DimensionDefinitionData(BaseModel):
    id: UUID
    variable_definition_id: UUID
    code: str
    name_fa: str
    sort_order: int
    indicators: list[IndicatorDefinitionData]


class VariableDefinitionData(BaseModel):
    id: UUID
    code: PGORVariableCode
    name_fa: str
    sort_order: int
    dimensions: list[DimensionDefinitionData]


class PGORDefinitionData(BaseModel):
    id: UUID
    code: str
    version: str
    status: PGORDefinitionStatus
    requirement_policy_status: RequirementPolicyStatus
    source_reference: str
    variables: list[VariableDefinitionData]


class PGORDefinitionResponse(BaseModel):
    data: PGORDefinitionData
