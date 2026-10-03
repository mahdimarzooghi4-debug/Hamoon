from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.pgor.domain.engine import EBand, PBand, PGORSnapshotStatus, RBand


@dataclass(frozen=True, slots=True)
class PGORSnapshot:
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
    bottleneck_variables: tuple[PGORVariableCode, ...]
    e_band: EBand
    p_band: PBand
    r_band: RBand
    completeness_ratio: Decimal | None
    data_quality_flags: tuple[str, ...]
    input_fingerprint: str
    calculated_at: datetime
    calculated_by: UUID


@dataclass(frozen=True, slots=True)
class PGORSnapshotInput:
    snapshot_id: UUID
    observation_id: UUID
    observation_version: int
    indicator_definition_id: UUID
    dimension_definition_id: UUID
    variable_code: PGORVariableCode
    raw_score_0_100: Decimal
    normalized_score: Decimal
