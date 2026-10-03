from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.observability.request_context import current_correlation_id, current_request_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.app.security.resource_scope import require_household_assignment
from hamoon.domains.assessment.infrastructure.repositories import (
    SqlAlchemyAcceptedObservationRepository,
    SqlAlchemyAssessmentRepository,
    SqlAlchemyIndicatorObservationRepository,
    SqlAlchemyObservationValidationRepository,
)
from hamoon.domains.pgor.api.schemas import (
    CalculatePGORRequest,
    DimensionDefinitionData,
    IndicatorDefinitionData,
    PGORDefinitionData,
    PGORDefinitionResponse,
    PGORSnapshotData,
    PGORSnapshotResponse,
    VariableDefinitionData,
)
from hamoon.domains.pgor.application.commands import CalculateOfficialPGORCommand
from hamoon.domains.pgor.application.handlers import CalculateOfficialPGORHandler
from hamoon.domains.pgor.domain.definitions import (
    PGORDimensionDefinition,
    PGORIndicatorDefinition,
)
from hamoon.domains.pgor.domain.errors import (
    FormulaVersionNotFoundError,
    PGORCalculationBlockedError,
)
from hamoon.domains.pgor.domain.snapshots import PGORSnapshot
from hamoon.domains.pgor.infrastructure.repositories import (
    SqlAlchemyPGORDefinitionRepository,
    SqlAlchemyPGORFormulaRepository,
    SqlAlchemyPGORSnapshotRepository,
)
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder

router = APIRouter(tags=["pgor"])


def _snapshot_data(snapshot: PGORSnapshot) -> PGORSnapshotData:
    return PGORSnapshotData(
        id=snapshot.id,
        household_id=snapshot.household_id,
        assessment_id=snapshot.assessment_id,
        definition_version_id=snapshot.definition_version_id,
        formula_version_id=snapshot.formula_version_id,
        engine_version=snapshot.engine_version,
        status=snapshot.status,
        p=snapshot.p,
        g=snapshot.g,
        o=snapshot.o,
        r=snapshot.r,
        e=snapshot.e,
        bottleneck_variables=list(snapshot.bottleneck_variables),
        e_band=snapshot.e_band,
        p_band=snapshot.p_band,
        r_band=snapshot.r_band,
        completeness_ratio=snapshot.completeness_ratio,
        data_quality_flags=list(snapshot.data_quality_flags),
        input_fingerprint=snapshot.input_fingerprint,
    )


@router.get(
    "/api/v1/pgor/definitions/active",
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


@router.post(
    "/api/v1/assessments/{assessment_id}/calculate-pgor",
    response_model=PGORSnapshotResponse,
)
async def calculate_official_pgor(
    assessment_id: UUID,
    body: CalculatePGORRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PGORSnapshotResponse:
    assessment = await SqlAlchemyAssessmentRepository(session).get(assessment_id)
    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    await require_household_assignment(
        session=session,
        context=context,
        household_id=assessment.household_id,
    )

    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    handler = CalculateOfficialPGORHandler(
        assessments=SqlAlchemyAssessmentRepository(session),
        definitions=SqlAlchemyPGORDefinitionRepository(session),
        accepted_observations=SqlAlchemyAcceptedObservationRepository(session),
        observations=SqlAlchemyIndicatorObservationRepository(session),
        validations=SqlAlchemyObservationValidationRepository(session),
        formulas=SqlAlchemyPGORFormulaRepository(session),
        snapshots=SqlAlchemyPGORSnapshotRepository(session),
        events=SqlAlchemyDomainEventRecorder(session),
        audits=SqlAlchemyAuditRecorder(session),
    )
    try:
        async with session.begin():
            snapshot = await handler.handle(
                CalculateOfficialPGORCommand(
                    assessment_id=assessment_id,
                    formula_version_id=body.formula_version_id,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except FormulaVersionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_FORMULA_VERSION"},
        ) from exc
    except PGORCalculationBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "PGOR_CALCULATION_BLOCKED", "reason": str(exc)},
        ) from exc

    return PGORSnapshotResponse(data=_snapshot_data(snapshot))


@router.get(
    "/api/v1/pgor/snapshots/{snapshot_id}",
    response_model=PGORSnapshotResponse,
)
async def get_snapshot(
    snapshot_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER, Role.MANAGER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PGORSnapshotResponse:
    snapshot = await SqlAlchemyPGORSnapshotRepository(session).get(snapshot_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    await require_household_assignment(
        session=session,
        context=context,
        household_id=snapshot.household_id,
    )
    return PGORSnapshotResponse(data=_snapshot_data(snapshot))
