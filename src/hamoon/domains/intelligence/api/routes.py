from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.config.settings import Settings, get_settings
from hamoon.app.observability.request_context import current_correlation_id, current_request_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.app.security.resource_scope import require_household_assignment
from hamoon.domains.intelligence.api.schemas import (
    AIDecisionData,
    AIDecisionResponse,
    ConfirmDiagnosisRequest,
    DecisionTraceData,
    DecisionTraceResponse,
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
from hamoon.domains.intelligence.domain.registry import ResolvedAIRoute
from hamoon.domains.intelligence.infrastructure.repositories import (
    SqlAlchemyAIDecisionRepository,
    SqlAlchemyAIRuntimeRegistryRepository,
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
from hamoon.infrastructure.ai.contracts import AITaskClass
from hamoon.infrastructure.ai.diagnosis_runtime import (
    DIAGNOSIS_V1_SCHEMA,
    GatewayDiagnosisAIClient,
    local_fake_diagnosis_policy,
)
from hamoon.infrastructure.ai.gateway import ProviderAIGateway
from hamoon.infrastructure.ai.providers.fake import FakeAIProvider
from hamoon.infrastructure.ai.providers.openai import OpenAIProvider
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


def _production_ai_client(
    *,
    settings: Settings,
    route: ResolvedAIRoute,
) -> GatewayDiagnosisAIClient:
    if route.routing_policy.provider_code != "OPENAI":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AI_PROVIDER_UNAVAILABLE"},
        )
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AI_PROVIDER_CREDENTIAL_MISSING"},
        )
    provider = OpenAIProvider(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout_seconds=settings.openai_timeout_seconds,
    )
    return GatewayDiagnosisAIClient(
        gateway=ProviderAIGateway(providers={"OPENAI": provider}),
        routing_policy=route.routing_policy,
        instructions=route.instructions,
    )


async def _resolve_diagnosis_ai_client(
    *,
    session: AsyncSession,
    settings: Settings,
) -> GatewayDiagnosisAIClient:
    if settings.environment.lower() in {"local", "test", "development"}:
        return _local_ai_client(settings)

    route = await SqlAlchemyAIRuntimeRegistryRepository(session).resolve_active_route(
        AITaskClass.DIAGNOSIS
    )
    if route is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AI_ROUTING_POLICY_NOT_FOUND"},
        )
    return _production_ai_client(settings=settings, route=route)


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
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    command = GenerateDiagnosisCommand(
        household_id=household_id,
        pgor_snapshot_id=body.pgor_snapshot_id,
        actor_id=context.actor_id,
        request_id=request_id,
        correlation_id=correlation_id,
    )

    try:
        async with session.begin():
            await require_household_assignment(
                session=session,
                context=context,
                household_id=household_id,
            )
            ai_client = await _resolve_diagnosis_ai_client(
                session=session,
                settings=settings,
            )
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
            prepared = await handler.prepare(command)

        result = await handler.infer(
            prepared=prepared,
            correlation_id=correlation_id,
        )

        async with session.begin():
            diagnosis, ai_decision = await handler.persist(
                command=command,
                prepared=prepared,
                result=result,
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
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    handler = ReviewDiagnosisHandler(
        diagnoses=SqlAlchemyDiagnosisRepository(session),
        ai_decisions=SqlAlchemyAIDecisionRepository(session),
        human_decisions=SqlAlchemyHumanDecisionRepository(session),
        feature_packages=SqlAlchemyFeaturePackageRepository(session),
        traces=SqlAlchemyDecisionTraceRepository(session),
        learning_signals=SqlAlchemyLearningSignalRepository(session),
        events=SqlAlchemyDomainEventRecorder(session),
        audits=SqlAlchemyAuditRecorder(session),
        output_schema=DIAGNOSIS_V1_SCHEMA,
    )
    try:
        async with session.begin():
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


@router.get(
    "/api/v1/ai/decisions/{decision_id}",
    response_model=AIDecisionResponse,
)
async def get_ai_decision(
    decision_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AIDecisionResponse:
    decision = await SqlAlchemyAIDecisionRepository(session).get(decision_id)
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    await require_household_assignment(
        session=session,
        context=context,
        household_id=decision.household_id,
    )
    return AIDecisionResponse(
        data=AIDecisionData(
            id=decision.id,
            household_id=decision.household_id,
            assessment_id=decision.assessment_id,
            feature_package_id=decision.feature_package_id,
            pgor_snapshot_id=decision.pgor_snapshot_id,
            decision_type=decision.decision_type,
            status=decision.status,
            provider_code=decision.provider_code,
            model_id=decision.model_id,
            model_alias=decision.model_alias,
            routing_policy_id=decision.routing_policy_id,
            routing_policy_version=decision.routing_policy_version,
            prompt_policy_version=decision.prompt_policy_version,
            output_schema_version=decision.output_schema_version,
            structured_output=decision.structured_output,
            trace_id=decision.trace_id,
            generated_at=decision.generated_at,
        )
    )

@router.get(
    "/api/v1/ai/decisions/{decision_id}/trace",
    response_model=DecisionTraceResponse,
)
async def get_ai_decision_trace(
    decision_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DecisionTraceResponse:
    decision = await SqlAlchemyAIDecisionRepository(session).get(decision_id)
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    await require_household_assignment(
        session=session,
        context=context,
        household_id=decision.household_id,
    )
    trace = await SqlAlchemyDecisionTraceRepository(session).get_by_ai_decision(
        decision_id
    )
    if trace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    return DecisionTraceResponse(
        data=DecisionTraceData(
            id=trace.id,
            household_id=trace.household_id,
            trace_type=trace.trace_type,
            state_fingerprint=trace.state_fingerprint,
            pgor_snapshot_id=trace.pgor_snapshot_id,
            feature_package_id=trace.feature_package_id,
            ai_decision_id=trace.ai_decision_id,
            human_decision_id=trace.human_decision_id,
            opened_at=trace.opened_at,
            closed_at=trace.closed_at,
        )
    )
