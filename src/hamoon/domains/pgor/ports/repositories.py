from typing import Protocol
from uuid import UUID

from hamoon.domains.pgor.domain.definitions import (
    PGORDefinitionBundle,
    PGORDefinitionVersion,
    PGORIndicatorDefinition,
)


class PGORDefinitionRepository(Protocol):
    async def get_active_bundle(self) -> PGORDefinitionBundle | None: ...

    async def get_version(self, definition_version_id: UUID) -> PGORDefinitionVersion | None: ...

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
