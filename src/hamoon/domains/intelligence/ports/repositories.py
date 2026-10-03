from typing import Protocol
from uuid import UUID

from hamoon.domains.intelligence.domain.entities import FeaturePackage


class FeaturePackageRepository(Protocol):
    async def add(self, package: FeaturePackage) -> None: ...

    async def get(self, package_id: UUID) -> FeaturePackage | None: ...

    async def get_by_snapshot(
        self,
        *,
        snapshot_id: UUID,
        schema_version: str,
    ) -> FeaturePackage | None: ...
