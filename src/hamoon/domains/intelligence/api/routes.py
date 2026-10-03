from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.config.settings import Settings, get_settings
from hamoon.app.observability.request_context import current_correlation_id, current_request_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.app.security.resource_scope import require_household_assignment
from hamoon.domains.intelligence.api.schemas import (
    ConfirmDiagnosisRequest,
    DiagnosisData,
    DiagnosisResponse,
    GenerateDiagnosisData,
    GenerateDiagnosisRequest,
    GenerateDiagnosisResponse,
    ReviewDiagnosisData,
    ReviewDiagnosisResponse,
    StructuredDiagnosisReviewRequest,
)
from hamoon.domains.intelligence.application.diagnosis_commands import (
    GenerateDiagnosisCommand,
    ReviewDiagnosisCommand,
)
from hamoon.domains.intelligence.application.diagnosis_handlers import (
    GenerateDiagnosisHandler,
    ReviewDiagnosisHandler,
)
from hamoon.domains.intelligence.domain.decisions import HumanDecisionAction
from hamoon.domains.intelligence.domain.errors import (
    DiagnosisGenerationError,
    DiagnosisNotFoundError,
    DiagnosisVersionConflictError,
    InvalidDiagnosisReviewError,
)
from hamoon.domains.intelligence.infrastructure.repositories import (
    SqlAlchemyAIDecisionRepository,
    SqlAlchemyDecisionTraceRepository,
    SqlAlchemyDiagnosisRepository,
    SqlAlchemyFeaturePackageRepository,
    SqlAlchemyHumanDecisionRepository,
    SqlAlchemyLearningSignalRepository,
)
from hamoon.domains.pgor.infrastructure.repositories import (
    SqlAlchemyPGORDefinitionRepository,
    SqlAlchemyPGORSnapshotRepository,
)
from hamoon.infrastructure.ai.diagnosis_runtime import (
    DIAGNOSIS_V1_SCHEMA,
    GatewayDiagnosisAIClient,
    local_fake_diagnosis_policy,
)
from hamoon.infrastructure.ai.gateway import ProviderAIGateway
from hamoon.infrastructure.ai.providers.fake import FakeAIProvider
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder

router = APIRouter(tags=["intelligence"])


def _local_ai_client(settings: Settings) -> GatewayDiagnosisAIClient:
    if settings.environment.lower() not in {"local", "test", "development"}:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AI_PROVIDER_UNAVAILABLE"},
        )
    return GatewayDiagnosisAIClient(
        gateway=ProviderAIGateway(providers={"FAKE": FakeAIProvider()}),
        routing_policy=local_fake_diagnosis_policy(),
    )


@router.post(
    "/api/v1/households/{household_id}/diagnoses/generate",
    response_model=GenerateDiagnosisResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_diagnosis(
    household_id: UUID,
    body: GenerateDiagnosisRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GenerateDiagnosisResponse:
    await require_household_assignment(
        session=session,
        context=context,
        household_id=household_id,
    )

    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    ai_client = _local_ai_client(settings)

    handler = GenerateDiagnosisHandler(
        snapshots=SqlAlchemyPGORSnapshotRepository(session),
        definitions=SqlAlchemyPGORDefinitionRepository(session),
        feature_packages=SqlAlchemyFeaturePackageRepository(session),
        ai_decisions=SqlAlchemyAIDecisionRepository(session),
        diagnoses=SqlAlchemyDiagnosisRepository(session),
        traces=SqlAlchemyDecisionTraceRepository(session),
        ai_client=ai_client,
        events=SqlAlchemyDomainEventRecorder(session),
        audits=SqlAlchemyAuditRecorder(session),
    )
    try:
        async with session.begin():
            diagnosis, ai_decision = await handler.handle(
                GenerateDiagnosisCommand(
                    household_id=household_id,
                    pgor_snapshot_id=body.pgor_snapshot_id,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except DiagnosisGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc

    return GenerateDiagnosisResponse(
        data=GenerateDiagnosisData(
            diagnosis_id=diagnosis.id,
            ai_decision_id=ai_decision.id,
            status=diagnosis.status,
            version=diagnosis.version,
            trace_id=ai_decision.trace_id,
        )
    )


@router.get(
    "/api/v1/diagnoses/{diagnosis_id}",
    response_model=DiagnosisResponse,
)
async def get_diagnosis(
    diagnosis_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DiagnosisResponse:
    diagnosis = await SqlAlchemyDiagnosisRepository(session).get(diagnosis_id)
    if diagnosis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    await require_household_assignment(
        session=session,
        context=context,
        household_id=diagnosis.household_id,
    )
    ai_decision = await SqlAlchemyAIDecisionRepository(session).get(
        diagnosis.ai_decision_id
    )
    if ai_decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )

    return DiagnosisResponse(
        data=DiagnosisData(
            id=diagnosis.id,
            household_id=diagnosis.household_id,
            ai_decision_id=diagnosis.ai_decision_id,
            status=diagnosis.status,
            version=diagnosis.version,
            machine_proposal=ai_decision.structured_output,
            accepted_payload=diagnosis.accepted_payload,
            created_at=diagnosis.created_at,
            reviewed_at=diagnosis.reviewed_at,
            reviewed_by=diagnosis.reviewed_by,
        )
    )


async def _review(
    *,
    diagnosis_id: UUID,
    action: HumanDecisionAction,
    body: ConfirmDiagnosisRequest,
    modified_payload: dict[str, JsonValue] | None,
    context: AuthorizationContext,
    session: AsyncSession,
) -> ReviewDiagnosisResponse:
    diagnosis = await SqlAlchemyDiagnosisRepository(session).get(diagnosis_id)
    if diagnosis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    await require_household_assignment(
        session=session,
        context=context,
        household_id=diagnosis.household_id,
    )

    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    handler = ReviewDiagnosisHandler(
        diagnoses=SqlAlchemyDiagnosisRepository(session),
        ai_decisions=SqlAlchemyAIDecisionRepository(session),
        human_decisions=SqlAlchemyHumanDecisionRepository(session),
        traces=SqlAlchemyDecisionTraceRepository(session),
        learning_signals=SqlAlchemyLearningSignalRepository(session),
        events=SqlAlchemyDomainEventRecorder(session),
        audits=SqlAlchemyAuditRecorder(session),
        output_schema=DIAGNOSIS_V1_SCHEMA,
    )
    try:
        async with session.begin():
            updated, human_decision, signal = await handler.handle(
                ReviewDiagnosisCommand(
                    diagnosis_id=diagnosis_id,
                    actor_id=context.actor_id,
                    action=action,
                    expected_version=body.expected_version,
                    reason_code=body.reason_code,
                    reason_text=body.reason_text,
                    modified_payload=modified_payload,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except DiagnosisVersionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "VERSION_CONFLICT"},
        ) from exc
    except (DiagnosisNotFoundError, InvalidDiagnosisReviewError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc

    return ReviewDiagnosisResponse(
        data=ReviewDiagnosisData(
            diagnosis_id=updated.id,
            ai_decision_id=updated.ai_decision_id,
            human_decision_id=human_decision.id,
            learning_signal_id=signal.id,
            action=human_decision.action,
            status=updated.status,
            version=updated.version,
            accepted_payload=updated.accepted_payload,
        )
    )


@router.post(
    "/api/v1/diagnoses/{diagnosis_id}/confirm",
    response_model=ReviewDiagnosisResponse,
)
async def confirm_diagnosis(
    diagnosis_id: UUID,
    body: ConfirmDiagnosisRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReviewDiagnosisResponse:
    return await _review(
        diagnosis_id=diagnosis_id,
        action=HumanDecisionAction.CONFIRM,
        body=body,
        modified_payload=None,
        context=context,
        session=session,
    )


@router.post(
    "/api/v1/diagnoses/{diagnosis_id}/modify",
    response_model=ReviewDiagnosisResponse,
)
async def modify_diagnosis(
    diagnosis_id: UUID,
    body: StructuredDiagnosisReviewRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReviewDiagnosisResponse:
    return await _review(
        diagnosis_id=diagnosis_id,
        action=HumanDecisionAction.MODIFY,
        body=body,
        modified_payload=body.modified_payload,
        context=context,
        session=session,
    )


@router.post(
    "/api/v1/diagnoses/{diagnosis_id}/replace",
    response_model=ReviewDiagnosisResponse,
)
async def replace_diagnosis(
    diagnosis_id: UUID,
    body: StructuredDiagnosisReviewRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReviewDiagnosisResponse:
    return await _review(
        diagnosis_id=diagnosis_id,
        action=HumanDecisionAction.REPLACE,
        body=body,
        modified_payload=body.modified_payload,
        context=context,
        session=session,
    )


@router.post(
    "/api/v1/diagnoses/{diagnosis_id}/reject",
    response_model=ReviewDiagnosisResponse,
)
async def reject_diagnosis(
    diagnosis_id: UUID,
    body: ConfirmDiagnosisRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReviewDiagnosisResponse:
    return await _review(
        diagnosis_id=diagnosis_id,
        action=HumanDecisionAction.REJECT,
        body=body,
        modified_payload=None,
        context=context,
        session=session,
    )


@router.post(
    "/api/v1/diagnoses/{diagnosis_id}/defer",
    response_model=ReviewDiagnosisResponse,
)
async def defer_diagnosis(
    diagnosis_id: UUID,
    body: ConfirmDiagnosisRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReviewDiagnosisResponse:
    return await _review(
        diagnosis_id=diagnosis_id,
        action=HumanDecisionAction.DEFER,
        body=body,
        modified_payload=None,
        context=context,
        session=session,
    )
