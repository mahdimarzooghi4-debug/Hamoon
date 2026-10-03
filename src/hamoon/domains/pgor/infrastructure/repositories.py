from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.pgor.domain.definitions import (
    PGORDefinitionBundle,
    PGORDefinitionStatus,
    PGORDefinitionVersion,
    PGORDimensionDefinition,
    PGORIndicatorDefinition,
    PGORVariableDefinition,
)
from hamoon.domains.pgor.infrastructure.models import (
    PGORDefinitionVersionModel,
    PGORDimensionDefinitionModel,
    PGORIndicatorDefinitionModel,
    PGORVariableDefinitionModel,
)


def _version(model: PGORDefinitionVersionModel) -> PGORDefinitionVersion:
    return PGORDefinitionVersion(
        id=model.id,
        code=model.code,
        version=model.version,
        status=model.status,
        requirement_policy_status=model.requirement_policy_status,
        source_reference=model.source_reference,
    )


def _variable(model: PGORVariableDefinitionModel) -> PGORVariableDefinition:
    return PGORVariableDefinition(
        id=model.id,
        definition_version_id=model.definition_version_id,
        code=model.code,
        name_fa=model.name_fa,
        sort_order=model.sort_order,
    )


def _dimension(model: PGORDimensionDefinitionModel) -> PGORDimensionDefinition:
    return PGORDimensionDefinition(
        id=model.id,
        variable_definition_id=model.variable_definition_id,
        code=model.code,
        name_fa=model.name_fa,
        sort_order=model.sort_order,
    )


def _indicator(model: PGORIndicatorDefinitionModel) -> PGORIndicatorDefinition:
    return PGORIndicatorDefinition(
        id=model.id,
        dimension_definition_id=model.dimension_definition_id,
        code=model.code,
        name_fa=model.name_fa,
        score_min=model.score_min,
        score_max=model.score_max,
        required_for_complete_assessment=model.required_for_complete_assessment,
        direct_dimension_measure=model.direct_dimension_measure,
        sort_order=model.sort_order,
    )


class SqlAlchemyPGORDefinitionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_bundle(self) -> PGORDefinitionBundle | None:
        result = await self._session.execute(
            select(PGORDefinitionVersionModel)
            .where(PGORDefinitionVersionModel.status == PGORDefinitionStatus.ACTIVE)
            .order_by(PGORDefinitionVersionModel.created_at.desc())
            .limit(1)
        )
        version_model = result.scalar_one_or_none()
        if version_model is None:
            return None

        variables_result = await self._session.execute(
            select(PGORVariableDefinitionModel)
            .where(
                PGORVariableDefinitionModel.definition_version_id == version_model.id
            )
            .order_by(PGORVariableDefinitionModel.sort_order)
        )
        variable_models = list(variables_result.scalars().all())
        variable_ids = [model.id for model in variable_models]

        dimensions_result = await self._session.execute(
            select(PGORDimensionDefinitionModel)
            .where(PGORDimensionDefinitionModel.variable_definition_id.in_(variable_ids))
            .order_by(PGORDimensionDefinitionModel.sort_order)
        )
        dimension_models = list(dimensions_result.scalars().all())
        dimension_ids = [model.id for model in dimension_models]

        indicators_result = await self._session.execute(
            select(PGORIndicatorDefinitionModel)
            .where(PGORIndicatorDefinitionModel.dimension_definition_id.in_(dimension_ids))
            .order_by(PGORIndicatorDefinitionModel.sort_order)
        )
        indicator_models = list(indicators_result.scalars().all())

        return PGORDefinitionBundle(
            version=_version(version_model),
            variables=tuple(_variable(model) for model in variable_models),
            dimensions=tuple(_dimension(model) for model in dimension_models),
            indicators=tuple(_indicator(model) for model in indicator_models),
        )

    async def get_version(
        self,
        definition_version_id: UUID,
    ) -> PGORDefinitionVersion | None:
        model = await self._session.get(
            PGORDefinitionVersionModel,
            definition_version_id,
        )
        return None if model is None else _version(model)

    async def list_indicators(
        self,
        definition_version_id: UUID,
    ) -> list[PGORIndicatorDefinition]:
        result = await self._session.execute(
            select(PGORIndicatorDefinitionModel)
            .join(
                PGORDimensionDefinitionModel,
                PGORDimensionDefinitionModel.id
                == PGORIndicatorDefinitionModel.dimension_definition_id,
            )
            .join(
                PGORVariableDefinitionModel,
                PGORVariableDefinitionModel.id
                == PGORDimensionDefinitionModel.variable_definition_id,
            )
            .where(
                PGORVariableDefinitionModel.definition_version_id
                == definition_version_id
            )
            .order_by(
                PGORVariableDefinitionModel.sort_order,
                PGORDimensionDefinitionModel.sort_order,
                PGORIndicatorDefinitionModel.sort_order,
            )
        )
        return [_indicator(model) for model in result.scalars().all()]

    async def get_indicator(
        self,
        *,
        definition_version_id: UUID,
        indicator_id: UUID,
    ) -> PGORIndicatorDefinition | None:
        result = await self._session.execute(
            select(PGORIndicatorDefinitionModel)
            .join(
                PGORDimensionDefinitionModel,
                PGORDimensionDefinitionModel.id
                == PGORIndicatorDefinitionModel.dimension_definition_id,
            )
            .join(
                PGORVariableDefinitionModel,
                PGORVariableDefinitionModel.id
                == PGORDimensionDefinitionModel.variable_definition_id,
            )
            .where(
                PGORVariableDefinitionModel.definition_version_id
                == definition_version_id,
                PGORIndicatorDefinitionModel.id == indicator_id,
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else _indicator(model)
