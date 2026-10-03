from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.intelligence.domain.entities import (
    FeaturePackage,
    FeatureValue,
    SensitivityClass,
)
from hamoon.domains.intelligence.infrastructure.models import (
    FeaturePackageModel,
    FeatureValueModel,
)


class SqlAlchemyFeaturePackageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, package: FeaturePackage) -> None:
        self._session.add(
            FeaturePackageModel(
                id=package.id,
                household_id=package.household_id,
                assessment_id=package.assessment_id,
                pgor_snapshot_id=package.pgor_snapshot_id,
                package_type=package.package_type,
                schema_version=package.schema_version,
                source_fingerprint=package.source_fingerprint,
                data_quality_flags=list(package.data_quality_flags),
                created_at=package.created_at,
                created_by=package.created_by,
            )
        )
        for order, value in enumerate(package.values, start=1):
            self._session.add(
                FeatureValueModel(
                    id=uuid4(),
                    feature_package_id=package.id,
                    feature_key=value.key,
                    value_json=value.value,
                    source_refs=list(value.source_refs),
                    sensitivity_class=value.sensitivity_class,
                    sort_order=order,
                )
            )

    async def _hydrate(self, model: FeaturePackageModel) -> FeaturePackage:
        result = await self._session.execute(
            select(FeatureValueModel)
            .where(FeatureValueModel.feature_package_id == model.id)
            .order_by(FeatureValueModel.sort_order)
        )
        values = tuple(
            FeatureValue(
                key=value.feature_key,
                value=value.value_json,
                source_refs=tuple(value.source_refs),
                sensitivity_class=SensitivityClass(value.sensitivity_class),
            )
            for value in result.scalars().all()
        )
        return FeaturePackage(
            id=model.id,
            household_id=model.household_id,
            assessment_id=model.assessment_id,
            pgor_snapshot_id=model.pgor_snapshot_id,
            package_type=model.package_type,
            schema_version=model.schema_version,
            source_fingerprint=model.source_fingerprint,
            data_quality_flags=tuple(model.data_quality_flags),
            values=values,
            created_at=model.created_at,
            created_by=model.created_by,
        )

    async def get(self, package_id: UUID) -> FeaturePackage | None:
        model = await self._session.get(FeaturePackageModel, package_id)
        return None if model is None else await self._hydrate(model)

    async def get_by_snapshot(
        self,
        *,
        snapshot_id: UUID,
        schema_version: str,
    ) -> FeaturePackage | None:
        result = await self._session.execute(
            select(FeaturePackageModel).where(
                FeaturePackageModel.pgor_snapshot_id == snapshot_id,
                FeaturePackageModel.schema_version == schema_version,
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else await self._hydrate(model)
