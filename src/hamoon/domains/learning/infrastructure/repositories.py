from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.intelligence.domain.decisions import LearningSignalType
from hamoon.domains.learning.domain.entities import (
    LearningDatasetItem,
    LearningDatasetVersion,
)
from hamoon.domains.learning.infrastructure.models import (
    LearningDatasetItemModel,
    LearningDatasetVersionModel,
)


def _dataset(model: LearningDatasetVersionModel) -> LearningDatasetVersion:
    return LearningDatasetVersion(
        id=model.id,
        dataset_key=model.dataset_key,
        version=model.version,
        purpose=model.purpose,
        selection_policy_version=model.selection_policy_version,
        status=model.status,
        manifest_ref=model.manifest_ref,
        manifest_digest=model.manifest_digest,
        created_at=model.created_at,
        created_by=model.created_by,
        approved_at=model.approved_at,
        approved_by=model.approved_by,
    )


def _item(model: LearningDatasetItemModel) -> LearningDatasetItem:
    return LearningDatasetItem(
        id=model.id,
        dataset_version_id=model.dataset_version_id,
        ordinal=model.ordinal,
        learning_signal_id=model.learning_signal_id,
        signal_type=LearningSignalType(model.signal_type),
        signal_label=model.signal_label,
        input_payload=model.input_payload,
        target_payload=model.target_payload,
        source_refs=tuple(model.source_refs),
    )


class SqlAlchemyLearningDatasetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        dataset: LearningDatasetVersion,
        items: tuple[LearningDatasetItem, ...],
    ) -> None:
        self._session.add(
            LearningDatasetVersionModel(
                id=dataset.id,
                dataset_key=dataset.dataset_key,
                version=dataset.version,
                purpose=dataset.purpose,
                selection_policy_version=dataset.selection_policy_version,
                status=dataset.status,
                manifest_ref=dataset.manifest_ref,
                manifest_digest=dataset.manifest_digest,
                created_at=dataset.created_at,
                created_by=dataset.created_by,
                approved_at=dataset.approved_at,
                approved_by=dataset.approved_by,
            )
        )
        for item in items:
            self._session.add(
                LearningDatasetItemModel(
                    id=item.id,
                    dataset_version_id=item.dataset_version_id,
                    ordinal=item.ordinal,
                    learning_signal_id=item.learning_signal_id,
                    signal_type=item.signal_type.value,
                    signal_label=item.signal_label,
                    input_payload=item.input_payload,
                    target_payload=item.target_payload,
                    source_refs=list(item.source_refs),
                )
            )

    async def get(self, dataset_id: UUID) -> LearningDatasetVersion | None:
        model = await self._session.get(LearningDatasetVersionModel, dataset_id)
        return None if model is None else _dataset(model)

    async def get_by_key_version(
        self,
        *,
        dataset_key: str,
        version: str,
    ) -> LearningDatasetVersion | None:
        result = await self._session.execute(
            select(LearningDatasetVersionModel).where(
                LearningDatasetVersionModel.dataset_key == dataset_key,
                LearningDatasetVersionModel.version == version,
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else _dataset(model)

    async def list_items(
        self,
        dataset_id: UUID,
    ) -> list[LearningDatasetItem]:
        result = await self._session.execute(
            select(LearningDatasetItemModel)
            .where(LearningDatasetItemModel.dataset_version_id == dataset_id)
            .order_by(LearningDatasetItemModel.ordinal)
        )
        return [_item(model) for model in result.scalars().all()]


    async def list_versions(
        self,
        *,
        status: DatasetVersionStatus | None = None,
        limit: int = 100,
    ) -> list[LearningDatasetVersion]:
        query = select(LearningDatasetVersionModel)
        if status is not None:
            query = query.where(LearningDatasetVersionModel.status == status)
        result = await self._session.execute(
            query.order_by(LearningDatasetVersionModel.created_at.desc()).limit(limit)
        )
        return [_dataset(model) for model in result.scalars().all()]

    async def item_counts(
        self,
        dataset_ids: list[UUID],
    ) -> dict[UUID, int]:
        if not dataset_ids:
            return {}
        result = await self._session.execute(
            select(
                LearningDatasetItemModel.dataset_version_id,
                func.count(LearningDatasetItemModel.id),
            )
            .where(LearningDatasetItemModel.dataset_version_id.in_(dataset_ids))
            .group_by(LearningDatasetItemModel.dataset_version_id)
        )
        return {
            dataset_id: int(count)
            for dataset_id, count in result.all()
        }

    async def approve(
        self,
        dataset: LearningDatasetVersion,
    ) -> None:
        model = await self._session.get(LearningDatasetVersionModel, dataset.id)
        if model is None:
            raise LookupError("LEARNING_DATASET_NOT_FOUND")
        if model.status != dataset.status and model.status.value != "DRAFT":
            raise ValueError("LEARNING_DATASET_STATUS_CHANGED")
        model.status = dataset.status
        model.approved_at = dataset.approved_at
        model.approved_by = dataset.approved_by
