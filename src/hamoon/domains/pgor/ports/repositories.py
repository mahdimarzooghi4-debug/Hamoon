from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from hamoon.domains.pgor.domain.definitions import (
    PGORDefinitionBundle,
    PGORDefinitionVersion,
    PGORIndicatorDefinition,
)
from hamoon.domains.pgor.domain.engine import (
    FormulaVersion,
    PGORCalculationResult,
    PGORSnapshotStatus,
)
from hamoon.domains.pgor.domain.snapshots import PGORSnapshot, PGORSnapshotInput


class PGORDefinitionRepository(Protocol):
    async def get_active_bundle(self) -> PGORDefinitionBundle | None: ...

    async def get_bundle(
        self,
        definition_version_id: UUID,
    ) -> PGORDefinitionBundle | None: ...

    async def get_version(
        self,
        definition_version_id: UUID,
    ) -> PGORDefinitionVersion | None: ...

    async def list_indicators(
        self,
        definition_version_id: UUID,
    ) -> list[PGORIndicatorDefinition]: ...

    async def get_indicator(
        self,
        *,
        definition_version_id: UUID,
        indicator_id: UUID,
    ) -> PGORIndicatorDefinition | None: ...


class PGORFormulaRepository(Protocol):
    async def get(self, formula_version_id: UUID) -> FormulaVersion | None: ...

    async def get_active(self) -> FormulaVersion | None: ...


class PGORSnapshotRepository(Protocol):
    async def create(
        self,
        *,
        household_id: UUID,
        assessment_id: UUID,
        definition_version_id: UUID,
        formula_version_id: UUID,
        engine_version: str,
        scoring_version: str,
        status: PGORSnapshotStatus,
        result: PGORCalculationResult,
        completeness_ratio: Decimal | None,
        data_quality_flags: tuple[str, ...],
        calculated_at: datetime,
        calculated_by: UUID,
    ) -> PGORSnapshot: ...

    async def get(self, snapshot_id: UUID) -> PGORSnapshot | None: ...

    async def list_inputs(self, snapshot_id: UUID) -> list[PGORSnapshotInput]: ...
