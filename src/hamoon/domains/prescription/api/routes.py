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
from hamoon.domains.family_data.infrastructure.repositories import (
    SqlAlchemyAcceptedStateRepository,
)
from hamoon.domains.intelligence.domain.decisions import HumanDecisionAction
from hamoon.domains.intelligence.infrastructure.repositories import (
    SqlAlchemyAIDecisionRepository,
    SqlAlchemyAIRuntimeRegistryRepository,
    SqlAlchemyDecisionTraceRepository,
    SqlAlchemyDiagnosisRepository,
    SqlAlchemyFeaturePackageRepository,
    SqlAlchemyHumanDecisionRepository,
    SqlAlchemyLearningSignalRepository,
)
from hamoon.domains.operations.infrastructure.repositories import (
    SqlAlchemyWorkItemRepository,
)
from hamoon.domains.pgor.infrastructure.repositories import (
    SqlAlchemyPGORSnapshotRepository,
)
from hamoon.domains.prescription.api.schemas import (
    GeneratePrescriptionData,
    GeneratePrescriptionRequest,
    GeneratePrescriptionResponse,
    PrescriptionData,
    PrescriptionHistoryEntryData,
    PrescriptionHistoryResponse,
    PrescriptionHumanDecisionData,
    PrescriptionItemData,
    PrescriptionResponse,
    PrescriptionReviewRequest,
    PrescriptionReviewResponse,
    PrescriptionReviewData,
    StructuredPrescriptionReviewRequest,
)
from hamoon.domains.prescription.application.commands import GeneratePrescriptionCommand
from hamoon.domains.prescription.application.handlers import GeneratePrescriptionHandler
from hamoon.domains.prescription.application.commands import ReviewPrescriptionCommand
from hamoon.domains.prescription.application.review import (
    PrescriptionReviewError,
    PrescriptionVersionConflictError,
    ReviewPrescriptionHandler,
)
from hamoon.domains.prescription.domain.entities import PrescriptionItem
from hamoon.domains.prescription.domain.errors import PrescriptionGenerationError
from hamoon.domains.prescription.infrastructure.repositories import (
    SqlAlchemyPrescriptionRepository,
)
from hamoon.infrastructure.ai.contracts import AITaskClass
from hamoon.infrastructure.ai.gateway import ProviderAIGateway
from hamoon.infrastructure.ai.prescription_runtime import (
    GatewayPrescriptionAIClient,
    PRESCRIPTION_V1_SCHEMA,
    local_fake_prescription_policy,
)
from hamoon.infrastructure.ai.providers.fake import FakeAIProvider
from hamoon.infrastructure.ai.production_factory import (
    NativeAIRuntimeConfigurationError,
    build_native_gateway,
)
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
    try:
        gateway = build_native_gateway(settings=settings, route=route)
    except NativeAIRuntimeConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": str(exc)},
        ) from exc
    return GatewayPrescriptionAIClient(
        gateway=gateway,
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
                accepted_state=SqlAlchemyAcceptedStateRepository(session),
                work_items=SqlAlchemyWorkItemRepository(session),
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
        code = str(exc)
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
                if code == "HOUSEHOLD_CONTEXT_VERSION_CONFLICT"
                else status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail={"code": code},
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
    "/api/v1/households/{household_id}/prescriptions",
    response_model=PrescriptionHistoryResponse,
)
async def list_household_prescriptions(
    household_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = 50,
) -> PrescriptionHistoryResponse:
    await require_household_assignment(
        session=session,
        context=context,
        household_id=household_id,
    )
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_LIMIT"},
        )

    repository = SqlAlchemyPrescriptionRepository(session)
    prescriptions = await repository.list_for_household(
        household_id,
        limit=limit,
    )
    prescription_ids = [item.id for item in prescriptions]
    ai_decisions = await SqlAlchemyAIDecisionRepository(session).list_by_ids(
        [item.ai_decision_id for item in prescriptions]
    )
    human_decisions = await SqlAlchemyHumanDecisionRepository(
        session
    ).list_for_prescriptions(prescription_ids)
    accepted_items = await repository.list_items_for_prescriptions(
        prescription_ids
    )

    data: list[PrescriptionHistoryEntryData] = []
    for prescription in prescriptions:
        ai_decision = ai_decisions.get(prescription.ai_decision_id)
        if ai_decision is None:
            continue
        data.append(
            PrescriptionHistoryEntryData(
                id=prescription.id,
                household_id=prescription.household_id,
                diagnosis_id=prescription.diagnosis_id,
                ai_decision_id=prescription.ai_decision_id,
                pgor_snapshot_id=prescription.pgor_snapshot_id,
                status=prescription.status,
                version=prescription.version,
                machine_proposal=ai_decision.structured_output,
                accepted_payload=prescription.accepted_payload,
                model_alias=ai_decision.model_alias,
                output_schema_version=ai_decision.output_schema_version,
                generated_at=ai_decision.generated_at,
                created_at=prescription.created_at,
                created_by=prescription.created_by,
                accepted_at=prescription.accepted_at,
                accepted_by=prescription.accepted_by,
                human_decisions=[
                    PrescriptionHumanDecisionData(
                        id=decision.id,
                        actor_id=decision.actor_id,
                        action=decision.action,
                        reason_code=decision.reason_code,
                        reason_text=decision.reason_text,
                        accepted_payload=decision.accepted_payload,
                        modified_payload=decision.modified_payload,
                        decided_at=decision.decided_at,
                    )
                    for decision in human_decisions.get(prescription.id, [])
                ],
                accepted_items=[
                    _item_data(item)
                    for item in accepted_items.get(prescription.id, [])
                ],
            )
        )
    return PrescriptionHistoryResponse(data=data)


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



def _item_data(item: PrescriptionItem) -> PrescriptionItemData:
    return PrescriptionItemData(
        id=item.id,
        source_code=item.source_code,
        intervention_type=item.intervention_type.value,
        target_pgor_variable=item.target_pgor_variable.value,
        priority=item.priority,
        success_criteria=list(item.success_criteria),
        review_after_days=item.review_after_days,
        review_rationale=item.review_rationale,
        rationale=item.rationale,
        title=item.title,
        status=item.status,
        machine_proposed=item.machine_proposed,
    )


async def _review_prescription(
    *,
    prescription_id: UUID,
    action: HumanDecisionAction,
    body: PrescriptionReviewRequest,
    modified_payload: dict[str, JsonValue] | None,
    context: AuthorizationContext,
    session: AsyncSession,
) -> PrescriptionReviewResponse:
    repository = SqlAlchemyPrescriptionRepository(session)
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    try:
        async with session.begin():
            prescription = await repository.get(prescription_id)
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
            updated, human, signal, items = await ReviewPrescriptionHandler(
                prescriptions=repository,
                ai_decisions=SqlAlchemyAIDecisionRepository(session),
                feature_packages=SqlAlchemyFeaturePackageRepository(session),
                human_decisions=SqlAlchemyHumanDecisionRepository(session),
                learning_signals=SqlAlchemyLearningSignalRepository(session),
                traces=SqlAlchemyDecisionTraceRepository(session),
                work_items=SqlAlchemyWorkItemRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
                output_schema=PRESCRIPTION_V1_SCHEMA,
            ).handle(
                ReviewPrescriptionCommand(
                    prescription_id=prescription_id,
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
    except PrescriptionVersionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "VERSION_CONFLICT"},
        ) from exc
    except PrescriptionReviewError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc

    return PrescriptionReviewResponse(
        data=PrescriptionReviewData(
            prescription_id=updated.id,
            ai_decision_id=updated.ai_decision_id,
            human_decision_id=human.id,
            learning_signal_id=signal.id,
            action=human.action,
            status=updated.status,
            version=updated.version,
            accepted_payload=updated.accepted_payload,
            accepted_items=[_item_data(item) for item in items],
        )
    )


@router.post(
    "/api/v1/prescriptions/{prescription_id}/approve",
    response_model=PrescriptionReviewResponse,
)
async def approve_prescription(
    prescription_id: UUID,
    body: PrescriptionReviewRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PrescriptionReviewResponse:
    return await _review_prescription(
        prescription_id=prescription_id,
        action=HumanDecisionAction.CONFIRM,
        body=body,
        modified_payload=None,
        context=context,
        session=session,
    )


@router.post(
    "/api/v1/prescriptions/{prescription_id}/modify",
    response_model=PrescriptionReviewResponse,
)
async def modify_prescription(
    prescription_id: UUID,
    body: StructuredPrescriptionReviewRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PrescriptionReviewResponse:
    return await _review_prescription(
        prescription_id=prescription_id,
        action=HumanDecisionAction.MODIFY,
        body=body,
        modified_payload=body.modified_payload,
        context=context,
        session=session,
    )


@router.post(
    "/api/v1/prescriptions/{prescription_id}/replace",
    response_model=PrescriptionReviewResponse,
)
async def replace_prescription(
    prescription_id: UUID,
    body: StructuredPrescriptionReviewRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PrescriptionReviewResponse:
    return await _review_prescription(
        prescription_id=prescription_id,
        action=HumanDecisionAction.REPLACE,
        body=body,
        modified_payload=body.modified_payload,
        context=context,
        session=session,
    )


@router.post(
    "/api/v1/prescriptions/{prescription_id}/defer",
    response_model=PrescriptionReviewResponse,
)
async def defer_prescription(
    prescription_id: UUID,
    body: PrescriptionReviewRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PrescriptionReviewResponse:
    return await _review_prescription(
        prescription_id=prescription_id,
        action=HumanDecisionAction.DEFER,
        body=body,
        modified_payload=None,
        context=context,
        session=session,
    )
