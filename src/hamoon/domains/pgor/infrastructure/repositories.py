from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

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
from hamoon.domains.pgor.domain.engine import (
    FormulaVersion,
    PGORCalculationResult,
    PGORSnapshotStatus,
)
from hamoon.domains.pgor.domain.snapshots import PGORSnapshot, PGORSnapshotInput
from hamoon.domains.pgor.infrastructure.models import (
    PGORDefinitionVersionModel,
    PGORDimensionDefinitionModel,
    PGORIndicatorDefinitionModel,
    PGORFormulaVersionModel,
    PGORSnapshotInputModel,
    PGORSnapshotModel,
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

    async def get_bundle(
        self,
        definition_version_id: UUID,
    ) -> PGORDefinitionBundle | None:
        version_model = await self._session.get(
            PGORDefinitionVersionModel,
            definition_version_id,
        )
        if version_model is None:
            return None

        variables_result = await self._session.execute(
            select(PGORVariableDefinitionModel)
            .where(
                PGORVariableDefinitionModel.definition_version_id
                == definition_version_id
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


def _formula(model: PGORFormulaVersionModel) -> FormulaVersion:
    return FormulaVersion(
        id=model.id,
        code=model.code,
        version=model.version,
        status=model.status,
        alpha=model.alpha,
        beta=model.beta,
        gamma=model.gamma,
        approved_at=model.approved_at,
        effective_from=model.effective_from,
        production_eligible=model.production_eligible,
    )


def _snapshot(model: PGORSnapshotModel) -> PGORSnapshot:
    from hamoon.domains.pgor.domain.definitions import PGORVariableCode

    return PGORSnapshot(
        id=model.id,
        household_id=model.household_id,
        assessment_id=model.assessment_id,
        definition_version_id=model.definition_version_id,
        formula_version_id=model.formula_version_id,
        engine_version=model.engine_version,
        scoring_version=model.scoring_version,
        status=model.status,
        p=model.p,
        g=model.g,
        o=model.o,
        r=model.r,
        e=model.e,
        bottleneck_variables=tuple(
            PGORVariableCode(value) for value in model.bottleneck_variables
        ),
        e_band=model.e_band,
        p_band=model.p_band,
        r_band=model.r_band,
        completeness_ratio=model.completeness_ratio,
        data_quality_flags=tuple(model.data_quality_flags),
        input_fingerprint=model.input_fingerprint,
        calculated_at=model.calculated_at,
        calculated_by=model.calculated_by,
    )


class SqlAlchemyPGORFormulaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, formula_version_id: UUID) -> FormulaVersion | None:
        model = await self._session.get(PGORFormulaVersionModel, formula_version_id)
        return None if model is None else _formula(model)

    async def get_active(self) -> FormulaVersion | None:
        result = await self._session.execute(
            select(PGORFormulaVersionModel)
            .where(
                PGORFormulaVersionModel.status == "ACTIVE",
                PGORFormulaVersionModel.production_eligible.is_(True),
            )
            .order_by(PGORFormulaVersionModel.effective_from.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return None if model is None else _formula(model)


class SqlAlchemyPGORSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
    ) -> PGORSnapshot:
        snapshot_id = uuid4()
        model = PGORSnapshotModel(
            id=snapshot_id,
            household_id=household_id,
            assessment_id=assessment_id,
            definition_version_id=definition_version_id,
            formula_version_id=formula_version_id,
            engine_version=engine_version,
            scoring_version=scoring_version,
            status=status,
            p=result.p,
            g=result.g,
            o=result.o,
            r=result.r,
            e=result.e,
            bottleneck_variables=[
                code.value for code in result.bottleneck_variables
            ],
            e_band=result.e_band,
            p_band=result.p_band,
            r_band=result.r_band,
            completeness_ratio=completeness_ratio,
            data_quality_flags=list(data_quality_flags),
            input_fingerprint=result.input_fingerprint,
            calculated_at=calculated_at,
            calculated_by=calculated_by,
        )
        self._session.add(model)

        for item in result.normalized_inputs:
            self._session.add(
                PGORSnapshotInputModel(
                    id=uuid4(),
                    snapshot_id=snapshot_id,
                    observation_id=item.observation_id,
                    observation_version=item.observation_version,
                    indicator_definition_id=item.indicator_definition_id,
                    dimension_definition_id=item.dimension_definition_id,
                    variable_code=item.variable_code,
                    raw_score_0_100=item.raw_score_0_100,
                    normalized_score=item.normalized_score,
                )
            )

        return _snapshot(model)

    async def get(self, snapshot_id: UUID) -> PGORSnapshot | None:
        model = await self._session.get(PGORSnapshotModel, snapshot_id)
        return None if model is None else _snapshot(model)

    async def list_inputs(self, snapshot_id: UUID) -> list[PGORSnapshotInput]:
        result = await self._session.execute(
            select(PGORSnapshotInputModel)
            .where(PGORSnapshotInputModel.snapshot_id == snapshot_id)
            .order_by(PGORSnapshotInputModel.indicator_definition_id)
        )
        return [
            PGORSnapshotInput(
                snapshot_id=model.snapshot_id,
                observation_id=model.observation_id,
                observation_version=model.observation_version,
                indicator_definition_id=model.indicator_definition_id,
                dimension_definition_id=model.dimension_definition_id,
                variable_code=model.variable_code,
                raw_score_0_100=model.raw_score_0_100,
                normalized_score=model.normalized_score,
            )
            for model in result.scalars().all()
        ]
