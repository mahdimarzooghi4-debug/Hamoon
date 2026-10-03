from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.domains.pgor.api.schemas import (
    DimensionDefinitionData,
    IndicatorDefinitionData,
    PGORDefinitionData,
    PGORDefinitionResponse,
    VariableDefinitionData,
)
from hamoon.domains.pgor.domain.definitions import (
    PGORDimensionDefinition,
    PGORIndicatorDefinition,
)
from hamoon.domains.pgor.infrastructure.repositories import (
    SqlAlchemyPGORDefinitionRepository,
)
from hamoon.infrastructure.db.session import get_db_session

router = APIRouter(prefix="/api/v1/pgor", tags=["pgor"])


@router.get(
    "/definitions/active",
    response_model=PGORDefinitionResponse,
)
async def get_active_definition(
    _context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER, Role.MANAGER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PGORDefinitionResponse:
    bundle = await SqlAlchemyPGORDefinitionRepository(session).get_active_bundle()
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PGOR_DEFINITION_NOT_FOUND"},
        )

    dimensions_by_variable: dict[UUID, list[PGORDimensionDefinition]] = {}
    indicators_by_dimension: dict[UUID, list[PGORIndicatorDefinition]] = {}

    for dimension in bundle.dimensions:
        dimensions_by_variable.setdefault(dimension.variable_definition_id, []).append(
            dimension
        )
    for indicator in bundle.indicators:
        indicators_by_dimension.setdefault(
            indicator.dimension_definition_id,
            [],
        ).append(indicator)

    variables: list[VariableDefinitionData] = []
    for variable in bundle.variables:
        dimensions: list[DimensionDefinitionData] = []
        for dimension in dimensions_by_variable.get(variable.id, []):
            dimensions.append(
                DimensionDefinitionData(
                    id=dimension.id,
                    variable_definition_id=dimension.variable_definition_id,
                    code=dimension.code,
                    name_fa=dimension.name_fa,
                    sort_order=dimension.sort_order,
                    indicators=[
                        IndicatorDefinitionData(
                            id=indicator.id,
                            dimension_definition_id=indicator.dimension_definition_id,
                            code=indicator.code,
                            name_fa=indicator.name_fa,
                            score_min=indicator.score_min,
                            score_max=indicator.score_max,
                            required_for_complete_assessment=(
                                indicator.required_for_complete_assessment
                            ),
                            direct_dimension_measure=indicator.direct_dimension_measure,
                            sort_order=indicator.sort_order,
                        )
                        for indicator in indicators_by_dimension.get(dimension.id, [])
                    ],
                )
            )
        variables.append(
            VariableDefinitionData(
                id=variable.id,
                code=variable.code,
                name_fa=variable.name_fa,
                sort_order=variable.sort_order,
                dimensions=dimensions,
            )
        )

    return PGORDefinitionResponse(
        data=PGORDefinitionData(
            id=bundle.version.id,
            code=bundle.version.code,
            version=bundle.version.version,
            status=bundle.version.status,
            requirement_policy_status=bundle.version.requirement_policy_status,
            source_reference=bundle.version.source_reference,
            variables=variables,
        )
    )
