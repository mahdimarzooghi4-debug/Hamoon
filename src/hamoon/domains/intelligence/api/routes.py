from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

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
from hamoon.domains.intelligence.api.schemas import (
    AIDecisionData,
    AIDecisionResponse,
    AIEvaluationRunData,
    AIEvaluationRunListResponse,
    AIEvaluationRunResponse,
    AIModelVersionCatalogData,
    AIModelVersionCatalogResponse,
    AIRoutingPolicyCatalogData,
    AIRoutingPolicyCatalogResponse,
    AIRoutingPolicyDraftData,
    AIRoutingPolicyDraftResponse,
    AIRoutingPromotionData,
    AIRoutingPromotionResponse,
    CreateAIRoutingPolicyRequest,
    CompleteAIEvaluationRequest,
    ConfirmDiagnosisRequest,
    DecisionTraceData,
    DecisionTraceResponse,
    DiagnosisData,
    DiagnosisHistoryEntryData,
    DiagnosisHistoryResponse,
    DiagnosisHumanDecisionData,
    DiagnosisResponse,
    GenerateDiagnosisData,
    GenerateDiagnosisRequest,
    GenerateDiagnosisResponse,
    ReviewDiagnosisData,
    PromptPolicyVersionCatalogData,
    PromptPolicyVersionCatalogResponse,
    ReviewDiagnosisResponse,
    StructuredDiagnosisReviewRequest,
    TrainNativeModelRequest,
    TrainNativeModelResponse,
)
from hamoon.domains.intelligence.application.diagnosis_commands import (
    GenerateDiagnosisCommand,
    ReviewDiagnosisCommand,
)
from hamoon.domains.intelligence.application.diagnosis_handlers import (
    GenerateDiagnosisHandler,
    ReviewDiagnosisHandler,
)
from hamoon.domains.intelligence.application.evaluation_governance import (
    attest_evaluation_report,
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
from hamoon.domains.learning.domain.entities import DatasetVersionStatus
from hamoon.domains.learning.infrastructure.repositories import (
    SqlAlchemyLearningDatasetRepository,
)
from hamoon.domains.operations.infrastructure.repositories import (
    SqlAlchemyWorkItemRepository,
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
from hamoon.infrastructure.ai.training import (
    NativeModelTrainingError,
    train_native_model,
)
from hamoon.infrastructure.ai.providers.fake import FakeAIProvider
from hamoon.infrastructure.ai.production_factory import (
    NativeAIRuntimeConfigurationError,
    build_native_gateway,
)
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord

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
    try:
        gateway = build_native_gateway(settings=settings, route=route)
    except NativeAIRuntimeConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": str(exc)},
        ) from exc
    return GatewayDiagnosisAIClient(
        gateway=gateway,
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
            diagnosis, ai_decision = await handler.persist(
                command=command,
                prepared=prepared,
                result=result,
            )
    except DiagnosisGenerationError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
                if code == "HOUSEHOLD_CONTEXT_VERSION_CONFLICT"
                else status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail={"code": code},
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
    "/api/v1/households/{household_id}/diagnoses",
    response_model=DiagnosisHistoryResponse,
)
async def list_household_diagnoses(
    household_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = 50,
) -> DiagnosisHistoryResponse:
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

    diagnoses = await SqlAlchemyDiagnosisRepository(session).list_for_household(
        household_id,
        limit=limit,
    )
    ai_decisions = await SqlAlchemyAIDecisionRepository(session).list_by_ids(
        [item.ai_decision_id for item in diagnoses]
    )
    human_decisions = await SqlAlchemyHumanDecisionRepository(
        session
    ).list_for_diagnoses([item.id for item in diagnoses])

    data: list[DiagnosisHistoryEntryData] = []
    for diagnosis in diagnoses:
        ai_decision = ai_decisions.get(diagnosis.ai_decision_id)
        if ai_decision is None:
            continue
        data.append(
            DiagnosisHistoryEntryData(
                id=diagnosis.id,
                household_id=diagnosis.household_id,
                ai_decision_id=diagnosis.ai_decision_id,
                status=diagnosis.status,
                version=diagnosis.version,
                machine_proposal=ai_decision.structured_output,
                accepted_payload=diagnosis.accepted_payload,
                model_alias=ai_decision.model_alias,
                output_schema_version=ai_decision.output_schema_version,
                generated_at=ai_decision.generated_at,
                created_at=diagnosis.created_at,
                reviewed_at=diagnosis.reviewed_at,
                reviewed_by=diagnosis.reviewed_by,
                human_decisions=[
                    DiagnosisHumanDecisionData(
                        id=decision.id,
                        actor_id=decision.actor_id,
                        action=decision.action,
                        reason_code=decision.reason_code,
                        reason_text=decision.reason_text,
                        accepted_payload=decision.accepted_payload,
                        modified_payload=decision.modified_payload,
                        decided_at=decision.decided_at,
                    )
                    for decision in human_decisions.get(diagnosis.id, [])
                ],
            )
        )
    return DiagnosisHistoryResponse(data=data)


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
        work_items=SqlAlchemyWorkItemRepository(session),
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
            model_artifact_sha256=decision.model_artifact_sha256,
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
            household_context_version=trace.household_context_version,
            pgor_snapshot_id=trace.pgor_snapshot_id,
            feature_package_id=trace.feature_package_id,
            ai_decision_id=trace.ai_decision_id,
            model_artifact_sha256=decision.model_artifact_sha256,
            human_decision_id=trace.human_decision_id,
            prescription_id=trace.prescription_id,
            intervention_id=trace.intervention_id,
            referral_id=trace.referral_id,
            provider_result_id=trace.provider_result_id,
            outcome_id=trace.outcome_id,
            learning_signal_id=trace.learning_signal_id,
            opened_at=trace.opened_at,
            closed_at=trace.closed_at,
        )
    )



@router.post(
    "/api/v1/admin/ai/native-models/train",
    response_model=TrainNativeModelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def train_native_ai_model(
    body: TrainNativeModelRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TrainNativeModelResponse:
    datasets = SqlAlchemyLearningDatasetRepository(session)
    async with session.begin():
        dataset = await datasets.get(body.dataset_version_id)
        if dataset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "LEARNING_DATASET_NOT_FOUND"},
            )
        if dataset.status is not DatasetVersionStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "TRAINING_DATASET_NOT_APPROVED"},
            )
        items = await datasets.list_items(dataset.id)
    try:
        _artifact, digest = train_native_model(
            model_root=settings.ai_model_root,
            task_class=body.task_class,
            model_id=body.model_id,
            dataset=dataset,
            items=items,
        )
    except NativeModelTrainingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc

    repository = SqlAlchemyAIRuntimeRegistryRepository(session)
    now = datetime.now(UTC)
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    try:
        async with session.begin():
            candidate = await repository.register_native_model_candidate(
                task_class=body.task_class,
                model_key=body.model_key,
                version=body.version,
                concrete_model_id=body.model_id,
                artifact_sha256=digest,
                limitations=body.limitations,
            )
            await SqlAlchemyAuditRecorder(session).record(
                AuditRecord(
                    id=uuid4(),
                    actor_id=context.actor_id,
                    action="ai.native_model.train",
                    resource_type="AI_MODEL_VERSION",
                    resource_id=candidate.id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    created_at=now,
                    purpose="AI_MODEL_TRAINING",
                    metadata={
                        "task_class": body.task_class.value,
                        "dataset_version_id": str(dataset.id),
                        "dataset_manifest_digest": dataset.manifest_digest,
                        "model_key": candidate.model_key,
                        "model_version": candidate.version,
                        "artifact_sha256": digest,
                        "provider_code": candidate.provider_code,
                    },
                )
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc

    return TrainNativeModelResponse(
        data=AIModelVersionCatalogData(
            id=candidate.id,
            ai_model_id=candidate.ai_model_id,
            model_key=candidate.model_key,
            purpose=candidate.purpose,
            provider_id=candidate.provider_id,
            provider_code=candidate.provider_code,
            provider_status=candidate.provider_status.value,
            version=candidate.version,
            concrete_model_id=candidate.concrete_model_id,
            artifact_sha256=candidate.artifact_sha256,
            status=candidate.status.value,
            limitations=candidate.limitations,
            approved_at=candidate.approved_at,
            deployed_at=candidate.deployed_at,
        )
    )


@router.get(
    "/api/v1/admin/ai/model-versions",
    response_model=AIModelVersionCatalogResponse,
)
async def list_ai_model_versions(
    _context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN, Role.SECURITY_AUDITOR)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AIModelVersionCatalogResponse:
    values = await SqlAlchemyAIRuntimeRegistryRepository(session).list_model_versions()
    return AIModelVersionCatalogResponse(
        data=[
            AIModelVersionCatalogData(
                id=item.id,
                ai_model_id=item.ai_model_id,
                model_key=item.model_key,
                purpose=item.purpose,
                provider_id=item.provider_id,
                provider_code=item.provider_code,
                provider_status=item.provider_status.value,
                version=item.version,
                concrete_model_id=item.concrete_model_id,
                artifact_sha256=item.artifact_sha256,
                status=item.status.value,
                limitations=item.limitations,
                approved_at=item.approved_at,
                deployed_at=item.deployed_at,
            )
            for item in values
        ]
    )


@router.get(
    "/api/v1/admin/ai/prompt-policy-versions",
    response_model=PromptPolicyVersionCatalogResponse,
)
async def list_prompt_policy_versions(
    _context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN, Role.SECURITY_AUDITOR)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PromptPolicyVersionCatalogResponse:
    values = await SqlAlchemyAIRuntimeRegistryRepository(
        session
    ).list_prompt_policy_versions()
    return PromptPolicyVersionCatalogResponse(
        data=[
            PromptPolicyVersionCatalogData(
                id=item.id,
                prompt_policy_id=item.prompt_policy_id,
                policy_name=item.policy_name,
                purpose=item.purpose,
                version=item.version,
                output_schema_version=item.output_schema_version,
                guardrail_version=item.guardrail_version,
                status=item.status.value,
                approved_at=item.approved_at,
            )
            for item in values
        ]
    )


@router.get(
    "/api/v1/admin/ai/evaluations",
    response_model=AIEvaluationRunListResponse,
)
async def list_ai_evaluations(
    _context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN, Role.SECURITY_AUDITOR)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    task_class: AITaskClass | None = None,
    limit: int = 100,
) -> AIEvaluationRunListResponse:
    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_LIMIT"},
        )
    values = await SqlAlchemyAIRuntimeRegistryRepository(
        session
    ).list_evaluation_runs(task_class=task_class, limit=limit)
    return AIEvaluationRunListResponse(
        data=[
            AIEvaluationRunData(
                id=item.id,
                task_class=item.task_class.value,
                model_version_id=item.model_version_id,
                prompt_policy_version_id=item.prompt_policy_version_id,
                evaluation_policy_version=item.evaluation_policy_version,
                dataset_version_id=item.dataset_version_id,
                dataset_manifest_digest=item.dataset_manifest_digest,
                report_digest=item.report_digest,
                status=item.status.value,
                passed=item.passed,
                summary_metrics=item.summary_metrics,
                started_at=item.started_at,
                completed_at=item.completed_at,
            )
            for item in values
        ]
    )


@router.get(
    "/api/v1/admin/ai/routing-policies",
    response_model=AIRoutingPolicyCatalogResponse,
)
async def list_ai_routing_policies(
    _context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN, Role.SECURITY_AUDITOR)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    task_class: AITaskClass | None = None,
    limit: int = 100,
) -> AIRoutingPolicyCatalogResponse:
    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_LIMIT"},
        )
    values = await SqlAlchemyAIRuntimeRegistryRepository(
        session
    ).list_routing_policies(task_class=task_class, limit=limit)
    return AIRoutingPolicyCatalogResponse(
        data=[
            AIRoutingPolicyCatalogData(
                id=item.id,
                task_class=item.task_class.value,
                version=item.version,
                model_alias=item.model_alias,
                model_version_id=item.model_version_id,
                prompt_policy_version_id=item.prompt_policy_version_id,
                evaluation_run_id=item.evaluation_run_id,
                structured_output_required=item.structured_output_required,
                status=item.status.value,
                approved_at=item.approved_at,
            )
            for item in values
        ]
    )


@router.post(
    "/api/v1/admin/ai/evaluations/{evaluation_run_id}/complete",
    response_model=AIEvaluationRunResponse,
)
async def complete_ai_evaluation(
    evaluation_run_id: UUID,
    body: CompleteAIEvaluationRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AIEvaluationRunResponse:
    repository = SqlAlchemyAIRuntimeRegistryRepository(session)
    now = datetime.now(UTC)
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    try:
        async with session.begin():
            pending = await repository.get_evaluation_run(evaluation_run_id)
            if pending is None:
                raise LookupError("EVALUATION_RUN_NOT_FOUND")
            attestation = attest_evaluation_report(
                task_class=pending.task_class,
                expected_policy_version=pending.evaluation_policy_version,
                report=dict(body.report),
            )
            evaluation = await repository.complete_evaluation_run(
                evaluation_run_id=evaluation_run_id,
                dataset_manifest_digest=body.dataset_manifest_digest,
                report_digest=attestation.report_digest,
                passed=attestation.passed,
                summary_metrics=attestation.summary_metrics,
                completed_at=now,
            )
            event_type = (
                "EvaluationRunCompleted"
                if evaluation.passed
                else "EvaluationRunFailed"
            )
            await SqlAlchemyDomainEventRecorder(session).record(
                DomainEventRecord(
                    event_id=uuid4(),
                    event_type=event_type,
                    event_version=1,
                    aggregate_type="EVALUATION_RUN",
                    aggregate_id=evaluation.id,
                    aggregate_version=1,
                    actor_id=context.actor_id,
                    occurred_at=now,
                    recorded_at=now,
                    correlation_id=correlation_id,
                    causation_id=None,
                    payload={
                        "task_class": evaluation.task_class.value,
                        "dataset_version_id": str(evaluation.dataset_version_id),
                        "dataset_manifest_digest": (
                            evaluation.dataset_manifest_digest
                        ),
                        "evaluation_policy_version": (
                            evaluation.evaluation_policy_version
                        ),
                        "report_digest": evaluation.report_digest,
                        "passed": evaluation.passed,
                    },
                )
            )
            await SqlAlchemyAuditRecorder(session).record(
                AuditRecord(
                    id=uuid4(),
                    actor_id=context.actor_id,
                    action="ai.evaluation.complete",
                    resource_type="EVALUATION_RUN",
                    resource_id=evaluation_run_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    created_at=now,
                    purpose="AI_MODEL_GOVERNANCE",
                    metadata={
                        "passed": evaluation.passed,
                        "evaluation_policy_version": (
                            evaluation.evaluation_policy_version
                        ),
                        "dataset_manifest_digest": (
                            evaluation.dataset_manifest_digest
                        ),
                        "report_digest": evaluation.report_digest,
                    },
                )
            )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc

    return AIEvaluationRunResponse(
        data=AIEvaluationRunData(
            id=evaluation.id,
            task_class=evaluation.task_class.value,
            model_version_id=evaluation.model_version_id,
            prompt_policy_version_id=evaluation.prompt_policy_version_id,
            evaluation_policy_version=evaluation.evaluation_policy_version,
            dataset_version_id=evaluation.dataset_version_id,
            dataset_manifest_digest=evaluation.dataset_manifest_digest,
            report_digest=evaluation.report_digest,
            status=evaluation.status.value,
            passed=evaluation.passed,
            summary_metrics=evaluation.summary_metrics,
            started_at=evaluation.started_at,
            completed_at=evaluation.completed_at,
        )
    )

@router.post(
    "/api/v1/admin/ai/routing-policies",
    response_model=AIRoutingPolicyDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_ai_routing_policy(
    body: CreateAIRoutingPolicyRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AIRoutingPolicyDraftResponse:
    repository = SqlAlchemyAIRuntimeRegistryRepository(session)
    now = datetime.now(UTC)
    try:
        async with session.begin():
            routing = await repository.create_routing_policy(
                task_class=body.task_class,
                version=body.version,
                model_alias=body.model_alias,
                model_version_id=body.model_version_id,
                prompt_policy_version_id=body.prompt_policy_version_id,
                evaluation_run_id=body.evaluation_run_id,
            )
            await SqlAlchemyAuditRecorder(session).record(
                AuditRecord(
                    id=uuid4(),
                    actor_id=context.actor_id,
                    action="ai.routing.create",
                    resource_type="MODEL_ROUTING_POLICY",
                    resource_id=routing.id,
                    request_id=current_request_id() or "unknown",
                    correlation_id=current_correlation_id()
                    or current_request_id()
                    or "unknown",
                    created_at=now,
                    purpose="AI_MODEL_GOVERNANCE",
                    metadata={
                        "task_class": routing.task_class.value,
                        "evaluation_run_id": str(routing.evaluation_run_id),
                        "model_version_id": str(routing.model_version_id),
                        "routing_version": routing.version,
                    },
                )
            )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc

    return AIRoutingPolicyDraftResponse(
        data=AIRoutingPolicyDraftData(
            routing_policy_id=routing.id,
            task_class=routing.task_class,
            version=routing.version,
            model_alias=routing.model_alias,
            model_version_id=routing.model_version_id,
            prompt_policy_version_id=routing.prompt_policy_version_id,
            evaluation_run_id=routing.evaluation_run_id,
            status=routing.status.value,
        )
    )


@router.post(
    "/api/v1/admin/ai/routing-policies/{routing_policy_id}/promote",
    response_model=AIRoutingPromotionResponse,
)
async def promote_ai_routing_policy(
    routing_policy_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AIRoutingPromotionResponse:
    repository = SqlAlchemyAIRuntimeRegistryRepository(session)
    now = datetime.now(UTC)
    try:
        async with session.begin():
            promoted = await repository.promote_routing_policy(
                routing_policy_id=routing_policy_id,
                activated_at=now,
            )
            await SqlAlchemyAuditRecorder(session).record(
                AuditRecord(
                    id=uuid4(),
                    actor_id=context.actor_id,
                    action="ai.routing.promote",
                    resource_type="MODEL_ROUTING_POLICY",
                    resource_id=routing_policy_id,
                    request_id=current_request_id() or "unknown",
                    correlation_id=current_correlation_id()
                    or current_request_id()
                    or "unknown",
                    created_at=now,
                    purpose="AI_MODEL_GOVERNANCE",
                    metadata={
                        "model_version_id": str(promoted.model_version_id),
                        "task_class": promoted.task_class.value,
                        "routing_version": promoted.routing_version,
                    },
                )
            )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc

    return AIRoutingPromotionResponse(
        data=AIRoutingPromotionData(
            routing_policy_id=promoted.routing_policy_id,
            model_version_id=promoted.model_version_id,
            task_class=promoted.task_class.value,
            routing_version=promoted.routing_version,
            model_status=promoted.model_status.value,
            routing_status=promoted.routing_status.value,
            activated_at=promoted.activated_at,
        )
    )
