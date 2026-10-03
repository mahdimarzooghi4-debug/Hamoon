from typing import Protocol
from uuid import UUID

from hamoon.domains.learning.domain.entities import (
    LearningDatasetItem,
    LearningDatasetVersion,
)


class LearningDatasetRepository(Protocol):
    async def add(
        self,
        dataset: LearningDatasetVersion,
        items: tuple[LearningDatasetItem, ...],
    ) -> None: ...

    async def get(self, dataset_id: UUID) -> LearningDatasetVersion | None: ...

    async def get_by_key_version(
        self,
        *,
        dataset_key: str,
        version: str,
    ) -> LearningDatasetVersion | None: ...

    async def list_items(
        self,
        dataset_id: UUID,
    ) -> list[LearningDatasetItem]: ...

    async def approve(
        self,
        dataset: LearningDatasetVersion,
    ) -> None: ...
