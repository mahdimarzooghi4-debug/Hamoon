from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class PGORVariableCode(StrEnum):
    P = "P"
    G = "G"
    O = "O"
    R = "R"


class PGORDefinitionStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


class RequirementPolicyStatus(StrEnum):
    UNRESOLVED = "UNRESOLVED"
    RESOLVED = "RESOLVED"


@dataclass(frozen=True, slots=True)
class PGORDefinitionVersion:
    id: UUID
    code: str
    version: str
    status: PGORDefinitionStatus
    requirement_policy_status: RequirementPolicyStatus
    source_reference: str


@dataclass(frozen=True, slots=True)
class PGORVariableDefinition:
    id: UUID
    definition_version_id: UUID
    code: PGORVariableCode
    name_fa: str
    sort_order: int


@dataclass(frozen=True, slots=True)
class PGORDimensionDefinition:
    id: UUID
    variable_definition_id: UUID
    code: str
    name_fa: str
    sort_order: int


@dataclass(frozen=True, slots=True)
class PGORIndicatorDefinition:
    id: UUID
    dimension_definition_id: UUID
    code: str
    name_fa: str
    score_min: int
    score_max: int
    required_for_complete_assessment: bool | None
    direct_dimension_measure: bool
    sort_order: int


@dataclass(frozen=True, slots=True)
class PGORDefinitionBundle:
    version: PGORDefinitionVersion
    variables: tuple[PGORVariableDefinition, ...]
    dimensions: tuple[PGORDimensionDefinition, ...]
    indicators: tuple[PGORIndicatorDefinition, ...]
