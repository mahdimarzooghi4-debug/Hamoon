from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.config.settings import Settings, get_settings
from hamoon.app.observability.request_context import current_correlation_id, current_request_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.app.security.resource_scope import require_household_assignment
from hamoon.domains.intelligence.infrastructure.repositories import (
    SqlAlchemyAIDecisionRepository,
    SqlAlchemyAIRuntimeRegistryRepository,
    SqlAlchemyDecisionTraceRepository,
    SqlAlchemyDiagnosisRepository,
    SqlAlchemyFeaturePackageRepository,
)
from hamoon.domains.pgor.infrastructure.repositories import (
    SqlAlchemyPGORSnapshotRepository,
)
from hamoon.domains.prescription.api.schemas import (
    GeneratePrescriptionData,
    GeneratePrescriptionRequest,
    GeneratePrescriptionResponse,
    PrescriptionData,
    PrescriptionResponse,
)
from hamoon.domains.prescription.application.commands import GeneratePrescriptionCommand
from hamoon.domains.prescription.application.handlers import GeneratePrescriptionHandler
from hamoon.domains.prescription.domain.errors import PrescriptionGenerationError
from hamoon.domains.prescription.infrastructure.repositories import (
    SqlAlchemyPrescriptionRepository,
)
from hamoon.infrastructure.ai.contracts import AITaskClass
from hamoon.infrastructure.ai.gateway import ProviderAIGateway
from hamoon.infrastructure.ai.prescription_runtime import (
    GatewayPrescriptionAIClient,
    local_fake_prescription_policy,
)
from hamoon.infrastructure.ai.providers.fake import FakeAIProvider
from hamoon.infrastructure.ai.providers.openai import OpenAIProvider
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder

router = APIRouter(tags=["prescription"])


async def _resolve_ai_client(
    *,
    session: AsyncSession,
    settings: Settings,
) -> GatewayPrescriptionAIClient:
    if settings.environment.lower() in {"local", "test", "development"}:
        return GatewayPrescriptionAIClient(
            gateway=ProviderAIGateway(providers={"FAKE": FakeAIProvider()}),
            routing_policy=local_fake_prescription_policy(),
        )

    route = await SqlAlchemyAIRuntimeRegistryRepository(session).resolve_active_route(
        AITaskClass.PRESCRIPTION
    )
    if route is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AI_ROUTING_POLICY_NOT_FOUND"},
        )
    if route.routing_policy.provider_code != "OPENAI" or not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AI_PROVIDER_UNAVAILABLE"},
        )
    provider = OpenAIProvider(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout_seconds=settings.openai_timeout_seconds,
    )
    return GatewayPrescriptionAIClient(
        gateway=ProviderAIGateway(providers={"OPENAI": provider}),
        routing_policy=route.routing_policy,
        instructions=route.instructions,
    )


@router.post(
    "/api/v1/households/{household_id}/prescriptions/generate",
    response_model=GeneratePrescriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_prescription(
    household_id: UUID,
    body: GeneratePrescriptionRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GeneratePrescriptionResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    command = GeneratePrescriptionCommand(
        household_id=household_id,
        diagnosis_id=body.diagnosis_id,
        pgor_snapshot_id=body.pgor_snapshot_id,
        actor_id=context.actor_id,
        request_id=request_id,
        correlation_id=correlation_id,
    )

    handler: GeneratePrescriptionHandler | None = None
    try:
        async with session.begin():
            await require_household_assignment(
                session=session,
                context=context,
                household_id=household_id,
            )
            ai_client = await _resolve_ai_client(session=session, settings=settings)
            handler = GeneratePrescriptionHandler(
                snapshots=SqlAlchemyPGORSnapshotRepository(session),
                diagnoses=SqlAlchemyDiagnosisRepository(session),
                ai_decisions=SqlAlchemyAIDecisionRepository(session),
                feature_packages=SqlAlchemyFeaturePackageRepository(session),
                prescriptions=SqlAlchemyPrescriptionRepository(session),
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
            prescription, ai_decision = await handler.persist(
                command=command,
                prepared=prepared,
                result=result,
            )
    except PrescriptionGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc

    return GeneratePrescriptionResponse(
        data=GeneratePrescriptionData(
            prescription_id=prescription.id,
            ai_decision_id=ai_decision.id,
            status=prescription.status,
            version=prescription.version,
            trace_id=ai_decision.trace_id,
        )
    )


@router.get(
    "/api/v1/prescriptions/{prescription_id}",
    response_model=PrescriptionResponse,
)
async def get_prescription(
    prescription_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PrescriptionResponse:
    prescription = await SqlAlchemyPrescriptionRepository(session).get(prescription_id)
    if prescription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    await require_household_assignment(
        session=session,
        context=context,
        household_id=prescription.household_id,
    )
    ai_decision = await SqlAlchemyAIDecisionRepository(session).get(
        prescription.ai_decision_id
    )
    if ai_decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    return PrescriptionResponse(
        data=PrescriptionData(
            id=prescription.id,
            household_id=prescription.household_id,
            diagnosis_id=prescription.diagnosis_id,
            ai_decision_id=prescription.ai_decision_id,
            pgor_snapshot_id=prescription.pgor_snapshot_id,
            status=prescription.status,
            version=prescription.version,
            machine_proposal=ai_decision.structured_output,
            accepted_payload=prescription.accepted_payload,
            created_at=prescription.created_at,
            created_by=prescription.created_by,
        )
    )
