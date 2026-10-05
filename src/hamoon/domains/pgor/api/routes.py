from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.config.settings import get_settings
from hamoon.app.observability.request_context import current_correlation_id, current_request_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.app.security.resource_scope import require_household_assignment
from hamoon.domains.assessment.domain.entities import AssessmentType
from hamoon.domains.assessment.infrastructure.repositories import (
    SqlAlchemyAcceptedObservationRepository,
    SqlAlchemyAssessmentRepository,
    SqlAlchemyIndicatorObservationRepository,
    SqlAlchemyObservationValidationRepository,
)
from hamoon.domains.operations.application.handlers import (
    CompleteWorkItemFromSourceHandler,
    EnsureWorkItemHandler,
    MarkPostPGORReadyHandler,
)
from hamoon.domains.operations.domain.entities import ReassessmentPlan, WorkItemType
from hamoon.domains.operations.infrastructure.repositories import (
    SqlAlchemyReassessmentPlanRepository,
    SqlAlchemyWorkItemRepository,
)
from hamoon.domains.pgor.api.schemas import (
    CalculatePGORRequest,
    DimensionDefinitionData,
    IndicatorDefinitionData,
    PGORDefinitionData,
    PGORDefinitionResponse,
    PGORSnapshotData,
    PGORSnapshotResponse,
    PGORTraceData,
    PGORTraceInputData,
    PGORTraceResponse,
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
from hamoon.infrastructure.temporal.reassessment_starter import (
    signal_post_pgor_best_effort,
)

router = APIRouter(tags=["pgor"])


def _snapshot_data(snapshot: PGORSnapshot) -> PGORSnapshotData:
    return PGORSnapshotData(
        id=snapshot.id,
        household_id=snapshot.household_id,
        assessment_id=snapshot.assessment_id,
        definition_version_id=snapshot.definition_version_id,
        formula_version_id=snapshot.formula_version_id,
        engine_version=snapshot.engine_version,
        scoring_version=snapshot.scoring_version,
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
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    plan: ReassessmentPlan | None = None
    assessment_household_id: UUID | None = None

    try:
        async with session.begin():
            assessments = SqlAlchemyAssessmentRepository(session)
            assessment = await assessments.get(assessment_id)
            if assessment is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "RESOURCE_NOT_FOUND"},
                )
            assessment_household_id = assessment.household_id
            await require_household_assignment(
                session=session,
                context=context,
                household_id=assessment.household_id,
            )

            snapshot = await CalculateOfficialPGORHandler(
                assessments=assessments,
                definitions=SqlAlchemyPGORDefinitionRepository(session),
                accepted_observations=SqlAlchemyAcceptedObservationRepository(session),
                observations=SqlAlchemyIndicatorObservationRepository(session),
                validations=SqlAlchemyObservationValidationRepository(session),
                formulas=SqlAlchemyPGORFormulaRepository(session),
                snapshots=SqlAlchemyPGORSnapshotRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                CalculateOfficialPGORCommand(
                    assessment_id=assessment_id,
                    formula_version_id=body.formula_version_id,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )

            await CompleteWorkItemFromSourceHandler(
                work_items=SqlAlchemyWorkItemRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                work_type=WorkItemType.DATA_COMPLETION,
                resource_type="ASSESSMENT",
                resource_id=assessment.id,
                actor_id=context.actor_id,
                request_id=request_id,
                correlation_id=correlation_id,
            )

            if (
                assessment.assessment_type is AssessmentType.OUTCOME_REASSESSMENT
                and assessment.provider_result_id is not None
            ):
                plan = await MarkPostPGORReadyHandler(
                    plans=SqlAlchemyReassessmentPlanRepository(session),
                    work_items=SqlAlchemyWorkItemRepository(session),
                    events=SqlAlchemyDomainEventRecorder(session),
                    audits=SqlAlchemyAuditRecorder(session),
                ).handle(
                    provider_result_id=assessment.provider_result_id,
                    assessment_id=assessment.id,
                    snapshot_id=snapshot.id,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
    except FormulaVersionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_FORMULA_VERSION"},
        ) from exc
    except PGORCalculationBlockedError as exc:
        reason = str(exc)
        if (
            "MISSING_REQUIRED_INDICATOR" in reason
            and assessment_household_id is not None
        ):
            async with session.begin():
                await EnsureWorkItemHandler(
                    work_items=SqlAlchemyWorkItemRepository(session),
                    events=SqlAlchemyDomainEventRecorder(session),
                    audits=SqlAlchemyAuditRecorder(session),
                ).handle(
                    household_id=assessment_household_id,
                    work_type=WorkItemType.DATA_COMPLETION,
                    resource_type="ASSESSMENT",
                    resource_id=assessment_id,
                    title="تکمیل داده‌های ضروری ارزیابی",
                    reason=(
                        "محاسبه PGOR به دلیل نبود داده ضروری مسدود شده است."
                    ),
                    priority=80,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    policy_version="assessment-data-completion-v1",
                )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "PGOR_CALCULATION_BLOCKED", "reason": reason},
        ) from exc
    except (LookupError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc

    if plan is not None:
        await signal_post_pgor_best_effort(
            plan=plan,
            settings=get_settings(),
        )

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



@router.get(
    "/api/v1/pgor/snapshots/{snapshot_id}/trace",
    response_model=PGORTraceResponse,
)
async def get_snapshot_trace(
    snapshot_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER, Role.MANAGER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PGORTraceResponse:
    snapshots = SqlAlchemyPGORSnapshotRepository(session)
    snapshot = await snapshots.get(snapshot_id)
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

    bundle = await SqlAlchemyPGORDefinitionRepository(session).get_bundle(
        snapshot.definition_version_id
    )
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "PGOR_TRACE_DEFINITION_NOT_FOUND"},
        )

    persisted_inputs = await snapshots.list_inputs(snapshot_id)
    dimensions = {item.id: item for item in bundle.dimensions}
    indicators = {item.id: item for item in bundle.indicators}
    variable_order = {item.code: item.sort_order for item in bundle.variables}
    dimension_order = {item.id: item.sort_order for item in bundle.dimensions}
    indicator_order = {item.id: item.sort_order for item in bundle.indicators}

    persisted_inputs.sort(
        key=lambda item: (
            variable_order.get(item.variable_code, 999),
            dimension_order.get(item.dimension_definition_id, 999),
            indicator_order.get(item.indicator_definition_id, 999),
            str(item.observation_id),
        )
    )

    trace_inputs: list[PGORTraceInputData] = []
    for item in persisted_inputs:
        dimension = dimensions.get(item.dimension_definition_id)
        indicator = indicators.get(item.indicator_definition_id)
        if dimension is None or indicator is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "PGOR_TRACE_REFERENCE_MISSING"},
            )
        trace_inputs.append(
            PGORTraceInputData(
                observation_id=item.observation_id,
                observation_version=item.observation_version,
                indicator_definition_id=item.indicator_definition_id,
                indicator_code=indicator.code,
                indicator_name_fa=indicator.name_fa,
                dimension_definition_id=item.dimension_definition_id,
                dimension_code=dimension.code,
                dimension_name_fa=dimension.name_fa,
                variable_code=item.variable_code,
                raw_score_0_100=item.raw_score_0_100,
                normalized_score=item.normalized_score,
            )
        )

    return PGORTraceResponse(
        data=PGORTraceData(
            snapshot_id=snapshot.id,
            household_id=snapshot.household_id,
            assessment_id=snapshot.assessment_id,
            definition_version_id=snapshot.definition_version_id,
            definition_version=bundle.version.version,
            formula_version_id=snapshot.formula_version_id,
            engine_version=snapshot.engine_version,
            scoring_version=snapshot.scoring_version,
            input_fingerprint=snapshot.input_fingerprint,
            calculated_at=snapshot.calculated_at,
            inputs=trace_inputs,
        )
    )
