from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from hamoon.domains.pgor.domain.definitions import (
    PGORDefinitionStatus,
    PGORVariableCode,
    RequirementPolicyStatus,
)
from hamoon.domains.pgor.domain.engine import EBand, PBand, PGORSnapshotStatus, RBand


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


class CalculatePGORRequest(BaseModel):
    formula_version_id: UUID


class PGORSnapshotData(BaseModel):
    id: UUID
    household_id: UUID
    assessment_id: UUID
    definition_version_id: UUID
    formula_version_id: UUID
    engine_version: str
    scoring_version: str
    status: PGORSnapshotStatus
    p: Decimal
    g: Decimal
    o: Decimal
    r: Decimal
    e: Decimal
    bottleneck_variables: list[PGORVariableCode]
    e_band: EBand
    p_band: PBand
    r_band: RBand
    completeness_ratio: Decimal | None
    data_quality_flags: list[str]
    input_fingerprint: str


class PGORSnapshotResponse(BaseModel):
    data: PGORSnapshotData
