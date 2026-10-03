from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.observability.request_context import current_correlation_id, current_request_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.app.security.resource_scope import require_household_assignment
from hamoon.domains.assessment.api.schemas import (
    AcceptedObservationData,
    AcceptedObservationResponse,
    AssessmentData,
    AssessmentReadinessData,
    AssessmentReadinessResponse,
    AssessmentResponse,
    ChangeObservationValidationRequest,
    ObservationData,
    ObservationResponse,
    ObservationValidationData,
    ObservationValidationResponse,
    RecordObservationRequest,
    ResolveAcceptedObservationRequest,
    StartAssessmentRequest,
)
from hamoon.domains.assessment.application.commands import (
    ChangeObservationValidationCommand,
    RecordIndicatorObservationCommand,
    ResolveAcceptedObservationCommand,
    StartAssessmentCommand,
)
from hamoon.domains.assessment.application.handlers import (
    ChangeObservationValidationHandler,
    EvaluateAssessmentReadinessHandler,
    RecordIndicatorObservationHandler,
    ResolveAcceptedObservationHandler,
    StartAssessmentHandler,
)
from hamoon.domains.assessment.domain.entities import Assessment
from hamoon.domains.assessment.domain.errors import (
    AcceptedObservationVersionConflictError,
    AssessmentNotFoundError,
    DefinitionNotAvailableError,
    IndicatorNotInDefinitionError,
    InvalidObservationScoreError,
    InvalidObservationValidationTransitionError,
    ObservationNotFoundError,
    ObservationNotValidatedError,
    ValidationVersionConflictError,
)
from hamoon.domains.assessment.infrastructure.repositories import (
    SqlAlchemyAcceptedObservationRepository,
    SqlAlchemyAssessmentRepository,
    SqlAlchemyIndicatorObservationRepository,
    SqlAlchemyObservationValidationRepository,
)
from hamoon.domains.family_data.infrastructure.repositories import (
    SqlAlchemyDataSourceRepository,
)
from hamoon.domains.pgor.infrastructure.repositories import (
    SqlAlchemyPGORDefinitionRepository,
)
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder

router = APIRouter(tags=["assessment"])


async def _assessment_with_scope(
    *,
    assessment_id: UUID,
    session: AsyncSession,
    context: AuthorizationContext,
) -> Assessment:
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
    return assessment


@router.post(
    "/api/v1/households/{household_id}/assessments",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_assessment(
    household_id: UUID,
    body: StartAssessmentRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AssessmentResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id

    handler = StartAssessmentHandler(
        assessments=SqlAlchemyAssessmentRepository(session),
        definitions=SqlAlchemyPGORDefinitionRepository(session),
        events=SqlAlchemyDomainEventRecorder(session),
        audits=SqlAlchemyAuditRecorder(session),
    )
    try:
        async with session.begin():
            await require_household_assignment(
                session=session,
                context=context,
                household_id=household_id,
            )
            assessment = await handler.handle(
                StartAssessmentCommand(
                    household_id=household_id,
                    actor_id=context.actor_id,
                    assessment_type=body.assessment_type,
                    definition_version_id=body.definition_version_id,
                    reason=body.reason,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except DefinitionNotAvailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "PGOR_DEFINITION_NOT_AVAILABLE"},
        ) from exc

    return AssessmentResponse(
        data=AssessmentData(
            id=assessment.id,
            household_id=assessment.household_id,
            assessment_type=assessment.assessment_type,
            definition_version_id=assessment.definition_version_id,
            status=assessment.status,
            version=assessment.version,
            started_at=assessment.started_at,
        )
    )


@router.get(
    "/api/v1/assessments/{assessment_id}",
    response_model=AssessmentResponse,
)
async def get_assessment(
    assessment_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AssessmentResponse:
    assessment = await _assessment_with_scope(
        assessment_id=assessment_id,
        session=session,
        context=context,
    )
    return AssessmentResponse(
        data=AssessmentData(
            id=assessment.id,
            household_id=assessment.household_id,
            assessment_type=assessment.assessment_type,
            definition_version_id=assessment.definition_version_id,
            status=assessment.status,
            version=assessment.version,
            started_at=assessment.started_at,
        )
    )


@router.post(
    "/api/v1/assessments/{assessment_id}/observations",
    response_model=ObservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_observation(
    assessment_id: UUID,
    body: RecordObservationRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ObservationResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id

    await _assessment_with_scope(
        assessment_id=assessment_id,
        session=session,
        context=context,
    )

    handler = RecordIndicatorObservationHandler(
        assessments=SqlAlchemyAssessmentRepository(session),
        definitions=SqlAlchemyPGORDefinitionRepository(session),
        sources=SqlAlchemyDataSourceRepository(session),
        observations=SqlAlchemyIndicatorObservationRepository(session),
        validations=SqlAlchemyObservationValidationRepository(session),
        events=SqlAlchemyDomainEventRecorder(session),
        audits=SqlAlchemyAuditRecorder(session),
    )
    try:
        async with session.begin():
            observation, validation = await handler.handle(
                RecordIndicatorObservationCommand(
                    assessment_id=assessment_id,
                    actor_id=context.actor_id,
                    indicator_definition_id=body.indicator_definition_id,
                    raw_score_0_100=body.raw_score_0_100,
                    source_id=body.source_id,
                    source_detail=body.source_detail,
                    effective_at=body.effective_at,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except (IndicatorNotInDefinitionError, DefinitionNotAvailableError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_ASSESSMENT_INPUT"},
        ) from exc
    except InvalidObservationScoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_RAW_SCORE"},
        ) from exc

    return ObservationResponse(
        data=ObservationData(
            id=observation.id,
            assessment_id=observation.assessment_id,
            indicator_definition_id=observation.indicator_definition_id,
            raw_score_0_100=observation.raw_score_0_100,
            source_id=observation.source_id,
            source_detail=observation.source_detail,
            effective_at=observation.effective_at,
            observed_at=observation.observed_at,
            validation_status=validation.status,
            validation_version=validation.version,
        )
    )


@router.post(
    "/api/v1/assessments/{assessment_id}/observations/{observation_id}/validation",
    response_model=ObservationValidationResponse,
)
async def change_observation_validation(
    assessment_id: UUID,
    observation_id: UUID,
    body: ChangeObservationValidationRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ObservationValidationResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id

    await _assessment_with_scope(
        assessment_id=assessment_id,
        session=session,
        context=context,
    )

    handler = ChangeObservationValidationHandler(
        observations=SqlAlchemyIndicatorObservationRepository(session),
        validations=SqlAlchemyObservationValidationRepository(session),
        events=SqlAlchemyDomainEventRecorder(session),
        audits=SqlAlchemyAuditRecorder(session),
    )
    try:
        async with session.begin():
            result = await handler.handle(
                ChangeObservationValidationCommand(
                    assessment_id=assessment_id,
                    observation_id=observation_id,
                    actor_id=context.actor_id,
                    to_status=body.to_status,
                    expected_validation_version=body.expected_validation_version,
                    reason_code=body.reason_code,
                    reason_text=body.reason_text,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except ObservationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        ) from exc
    except InvalidObservationValidationTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_OBSERVATION_VALIDATION_TRANSITION"},
        ) from exc
    except ValidationVersionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "VERSION_CONFLICT"},
        ) from exc

    return ObservationValidationResponse(
        data=ObservationValidationData(
            observation_id=result.observation_id,
            status=result.status,
            version=result.version,
            changed_at=result.changed_at,
            reason_code=result.reason_code,
            reason_text=result.reason_text,
        )
    )


@router.post(
    "/api/v1/assessments/{assessment_id}/accepted-observations/{indicator_id}/resolve",
    response_model=AcceptedObservationResponse,
)
async def resolve_accepted_observation(
    assessment_id: UUID,
    indicator_id: UUID,
    body: ResolveAcceptedObservationRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AcceptedObservationResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id

    await _assessment_with_scope(
        assessment_id=assessment_id,
        session=session,
        context=context,
    )

    handler = ResolveAcceptedObservationHandler(
        observations=SqlAlchemyIndicatorObservationRepository(session),
        validations=SqlAlchemyObservationValidationRepository(session),
        accepted_observations=SqlAlchemyAcceptedObservationRepository(session),
        events=SqlAlchemyDomainEventRecorder(session),
        audits=SqlAlchemyAuditRecorder(session),
    )
    try:
        async with session.begin():
            result = await handler.handle(
                ResolveAcceptedObservationCommand(
                    assessment_id=assessment_id,
                    indicator_definition_id=indicator_id,
                    observation_id=body.observation_id,
                    actor_id=context.actor_id,
                    expected_projection_version=body.expected_projection_version,
                    reason_code=body.reason_code,
                    reason_text=body.reason_text,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except ObservationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        ) from exc
    except (IndicatorNotInDefinitionError, ObservationNotValidatedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "OBSERVATION_NOT_ELIGIBLE_FOR_ACCEPTANCE"},
        ) from exc
    except AcceptedObservationVersionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "VERSION_CONFLICT"},
        ) from exc

    return AcceptedObservationResponse(
        data=AcceptedObservationData(
            assessment_id=result.assessment_id,
            indicator_definition_id=result.indicator_definition_id,
            observation_id=result.observation_id,
            projection_version=result.projection_version,
            changed_at=result.changed_at,
        )
    )


@router.get(
    "/api/v1/assessments/{assessment_id}/readiness",
    response_model=AssessmentReadinessResponse,
)
async def get_assessment_readiness(
    assessment_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AssessmentReadinessResponse:
    await _assessment_with_scope(
        assessment_id=assessment_id,
        session=session,
        context=context,
    )
    result = await EvaluateAssessmentReadinessHandler(
        assessments=SqlAlchemyAssessmentRepository(session),
        definitions=SqlAlchemyPGORDefinitionRepository(session),
        accepted_observations=SqlAlchemyAcceptedObservationRepository(session),
        validations=SqlAlchemyObservationValidationRepository(session),
    ).handle(assessment_id)

    return AssessmentReadinessResponse(
        data=AssessmentReadinessData(
            assessment_id=result.assessment_id,
            status=result.status,
            total_indicator_count=result.total_indicator_count,
            accepted_indicator_count=result.accepted_indicator_count,
            required_indicator_count=result.required_indicator_count,
            accepted_required_indicator_count=result.accepted_required_indicator_count,
            completeness_ratio=result.completeness_ratio,
            missing_required_indicator_ids=list(result.missing_required_indicator_ids),
            unresolved_validation_count=result.unresolved_validation_count,
            blocking_reasons=list(result.blocking_reasons),
            accepted_observation_ids=list(result.accepted_observation_ids),
        )
    )
