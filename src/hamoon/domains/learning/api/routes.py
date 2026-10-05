from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.observability.request_context import current_correlation_id, current_request_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.domains.intelligence.api.schemas import (
    AIEvaluationRunData,
    AIEvaluationRunResponse,
)
from hamoon.domains.intelligence.domain.decisions import (
    LearningSignal,
    LearningSignalQuality,
    LearningSignalType,
)
from hamoon.domains.intelligence.infrastructure.repositories import (
    SqlAlchemyAIRuntimeRegistryRepository,
    SqlAlchemyLearningSignalRepository,
)
from hamoon.domains.intervention.infrastructure.repositories import (
    SqlAlchemyInterventionRepository,
)
from hamoon.domains.learning.api.schemas import (
    CreateEvaluationRunRequest,
    CreateOutcomeDatasetRequest,
    CurateLearningSignalRequest,
    LearningDatasetData,
    LearningDatasetExportCase,
    LearningDatasetExportData,
    LearningDatasetExportResponse,
    LearningDatasetListResponse,
    LearningDatasetResponse,
    LearningSignalData,
    LearningSignalListResponse,
    LearningSignalResponse,
)
from hamoon.domains.learning.application.commands import (
    ApproveDatasetCommand,
    CreateEvaluationRunCommand,
    CreateOutcomeDatasetCommand,
    CurateLearningSignalCommand,
)
from hamoon.domains.learning.application.handlers import (
    ApproveDatasetHandler,
    CreateEvaluationRunHandler,
    CreateOutcomeDatasetHandler,
    CurateLearningSignalHandler,
)
from hamoon.domains.learning.domain.entities import DatasetVersionStatus
from hamoon.domains.learning.domain.errors import (
    LearningCurationError,
    LearningDatasetError,
)
from hamoon.domains.learning.infrastructure.repositories import (
    SqlAlchemyLearningDatasetRepository,
)
from hamoon.domains.outcome.infrastructure.repositories import (
    SqlAlchemyOutcomeRepository,
)
from hamoon.domains.pgor.infrastructure.repositories import (
    SqlAlchemyPGORSnapshotRepository,
)
from hamoon.domains.provider_result.infrastructure.repositories import (
    SqlAlchemyProviderResultRepository,
)
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder

router = APIRouter(tags=["learning"])


def _signal_data(signal: LearningSignal) -> LearningSignalData:
    return LearningSignalData(
        id=signal.id,
        household_id=signal.household_id,
        signal_type=signal.signal_type,
        ai_decision_id=signal.ai_decision_id,
        human_decision_id=signal.human_decision_id,
        diagnosis_id=signal.diagnosis_id,
        prescription_id=signal.prescription_id,
        intervention_id=signal.intervention_id,
        provider_match_id=signal.provider_match_id,
        provider_id=signal.provider_id,
        provider_result_id=signal.provider_result_id,
        outcome_id=signal.outcome_id,
        signal_label=signal.signal_label,
        quality_status=signal.quality_status,
        created_at=signal.created_at,
    )


@router.get(
    "/api/v1/learning/signals",
    response_model=LearningSignalListResponse,
)
async def list_learning_signals(
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN, Role.SECURITY_AUDITOR)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    quality_status: Annotated[
        LearningSignalQuality | None,
        Query(),
    ] = None,
    signal_type: Annotated[
        LearningSignalType | None,
        Query(),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> LearningSignalListResponse:
    _ = context
    values = await SqlAlchemyLearningSignalRepository(session).list(
        quality_status=quality_status,
        signal_type=signal_type,
        limit=limit,
    )
    return LearningSignalListResponse(data=[_signal_data(item) for item in values])


@router.get(
    "/api/v1/learning/signals/{signal_id}",
    response_model=LearningSignalResponse,
)
async def get_learning_signal(
    signal_id: UUID,
    _context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN, Role.SECURITY_AUDITOR)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LearningSignalResponse:
    signal = await SqlAlchemyLearningSignalRepository(session).get(signal_id)
    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    return LearningSignalResponse(data=_signal_data(signal))


@router.post(
    "/api/v1/admin/learning/signals/{signal_id}/quality",
    response_model=LearningSignalResponse,
)
async def curate_learning_signal(
    signal_id: UUID,
    body: CurateLearningSignalRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LearningSignalResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    try:
        async with session.begin():
            signal = await CurateLearningSignalHandler(
                signals=SqlAlchemyLearningSignalRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                CurateLearningSignalCommand(
                    signal_id=signal_id,
                    expected_quality_status=body.expected_quality_status,
                    to_quality_status=body.to_quality_status,
                    reason_code=body.reason_code,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except LearningCurationError as exc:
        code = str(exc)
        http_status = (
            status.HTTP_409_CONFLICT
            if code == "LEARNING_SIGNAL_QUALITY_CONFLICT"
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(
            status_code=http_status,
            detail={"code": code},
        ) from exc
    return LearningSignalResponse(data=_signal_data(signal))


@router.get(
    "/api/v1/admin/learning/datasets",
    response_model=LearningDatasetListResponse,
)
async def list_learning_datasets(
    _context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN, Role.SECURITY_AUDITOR)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    dataset_status: Annotated[
        DatasetVersionStatus | None,
        Query(alias="status"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> LearningDatasetListResponse:
    repository = SqlAlchemyLearningDatasetRepository(session)
    datasets = await repository.list_versions(
        status=dataset_status,
        limit=limit,
    )
    counts = await repository.item_counts([item.id for item in datasets])
    return LearningDatasetListResponse(
        data=[
            LearningDatasetData(
                id=dataset.id,
                dataset_key=dataset.dataset_key,
                version=dataset.version,
                purpose=dataset.purpose,
                selection_policy_version=dataset.selection_policy_version,
                status=dataset.status,
                manifest_ref=dataset.manifest_ref,
                manifest_digest=dataset.manifest_digest,
                item_count=counts.get(dataset.id, 0),
                created_at=dataset.created_at,
                created_by=dataset.created_by,
                approved_at=dataset.approved_at,
                approved_by=dataset.approved_by,
            )
            for dataset in datasets
        ]
    )


@router.post(
    "/api/v1/admin/learning/datasets",
    response_model=LearningDatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_learning_dataset(
    body: CreateOutcomeDatasetRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LearningDatasetResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    repository = SqlAlchemyLearningDatasetRepository(session)
    try:
        async with session.begin():
            dataset, items = await CreateOutcomeDatasetHandler(
                signals=SqlAlchemyLearningSignalRepository(session),
                datasets=repository,
                outcomes=SqlAlchemyOutcomeRepository(session),
                snapshots=SqlAlchemyPGORSnapshotRepository(session),
                interventions=SqlAlchemyInterventionRepository(session),
                provider_results=SqlAlchemyProviderResultRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                CreateOutcomeDatasetCommand(
                    dataset_key=body.dataset_key,
                    version=body.version,
                    selection_policy_version=body.selection_policy_version,
                    signal_ids=tuple(body.signal_ids),
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except LearningDatasetError as exc:
        code = str(exc)
        http_status = (
            status.HTTP_409_CONFLICT
            if code == "DATASET_VERSION_ALREADY_EXISTS"
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=http_status, detail={"code": code}) from exc
    return LearningDatasetResponse(
        data=LearningDatasetData(
            id=dataset.id,
            dataset_key=dataset.dataset_key,
            version=dataset.version,
            purpose=dataset.purpose,
            selection_policy_version=dataset.selection_policy_version,
            status=dataset.status,
            manifest_ref=dataset.manifest_ref,
            manifest_digest=dataset.manifest_digest,
            item_count=len(items),
            created_at=dataset.created_at,
            created_by=dataset.created_by,
            approved_at=dataset.approved_at,
            approved_by=dataset.approved_by,
        )
    )


@router.post(
    "/api/v1/admin/learning/datasets/{dataset_id}/approve",
    response_model=LearningDatasetResponse,
)
async def approve_learning_dataset(
    dataset_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LearningDatasetResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    repository = SqlAlchemyLearningDatasetRepository(session)
    try:
        async with session.begin():
            dataset = await ApproveDatasetHandler(
                datasets=repository,
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                ApproveDatasetCommand(
                    dataset_id=dataset_id,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
            items = await repository.list_items(dataset.id)
    except LearningDatasetError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc
    return LearningDatasetResponse(
        data=LearningDatasetData(
            id=dataset.id,
            dataset_key=dataset.dataset_key,
            version=dataset.version,
            purpose=dataset.purpose,
            selection_policy_version=dataset.selection_policy_version,
            status=dataset.status,
            manifest_ref=dataset.manifest_ref,
            manifest_digest=dataset.manifest_digest,
            item_count=len(items),
            created_at=dataset.created_at,
            created_by=dataset.created_by,
            approved_at=dataset.approved_at,
            approved_by=dataset.approved_by,
        )
    )


@router.get(
    "/api/v1/admin/learning/datasets/{dataset_id}/export",
    response_model=LearningDatasetExportResponse,
)
async def export_learning_dataset(
    dataset_id: UUID,
    _context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LearningDatasetExportResponse:
    repository = SqlAlchemyLearningDatasetRepository(session)
    dataset = await repository.get(dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    items = await repository.list_items(dataset.id)
    cases: list[LearningDatasetExportCase] = []
    for item in items:
        classification = item.target_payload.get("classification")
        if not isinstance(classification, str):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "LEARNING_DATASET_TARGET_INVALID"},
            )
        cases.append(
            LearningDatasetExportCase(
                case_id=str(item.id),
                input=item.input_payload,
                expert_classification=classification,
                source_refs=list(item.source_refs),
            )
        )
    return LearningDatasetExportResponse(
        data=LearningDatasetExportData(
            dataset_id=dataset.id,
            dataset_version=dataset.version,
            status=dataset.status,
            manifest_digest=dataset.manifest_digest,
            selection_policy_version=dataset.selection_policy_version,
            cases=cases,
        )
    )


@router.post(
    "/api/v1/admin/ai/evaluations",
    response_model=AIEvaluationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_ai_evaluation(
    body: CreateEvaluationRunRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.ADMIN)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AIEvaluationRunResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    try:
        async with session.begin():
            evaluation = await CreateEvaluationRunHandler(
                datasets=SqlAlchemyLearningDatasetRepository(session),
                registry=SqlAlchemyAIRuntimeRegistryRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                CreateEvaluationRunCommand(
                    task_class=body.task_class,
                    model_version_id=body.model_version_id,
                    prompt_policy_version_id=body.prompt_policy_version_id,
                    dataset_version_id=body.dataset_version_id,
                    evaluation_policy_version=body.evaluation_policy_version,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except LearningDatasetError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": str(exc)},
        ) from exc
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": str(exc)},
        ) from exc
    return AIEvaluationRunResponse(
        data=AIEvaluationRunData(
            id=evaluation.id,
            task_class=evaluation.task_class.value,
            model_version_id=evaluation.model_version_id,
            prompt_policy_version_id=evaluation.prompt_policy_version_id,
            dataset_version_id=evaluation.dataset_version_id,
            dataset_manifest_digest=evaluation.dataset_manifest_digest,
            report_digest=evaluation.report_digest,
            evaluation_policy_version=evaluation.evaluation_policy_version,
            status=evaluation.status.value,
            passed=evaluation.passed,
            summary_metrics=evaluation.summary_metrics,
            started_at=evaluation.started_at,
            completed_at=evaluation.completed_at,
        )
    )
