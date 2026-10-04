from pathlib import Path
from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from hamoon.app.config.settings import Settings, get_settings
from hamoon.app.observability.request_context import current_correlation_id, current_request_id
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.dependencies import require_roles
from hamoon.app.security.resource_scope import require_household_assignment
from hamoon.domains.evidence.api.schemas import (
    EvidenceData,
    EvidenceDownloadData,
    EvidenceDownloadResponse,
    EvidenceResponse,
    FinalizeEvidenceRequest,
    InitEvidenceUploadData,
    InitEvidenceUploadRequest,
    InitEvidenceUploadResponse,
)
from hamoon.domains.evidence.application.commands import (
    FinalizeEvidenceCommand,
    InitEvidenceUploadCommand,
    IssueEvidenceDownloadCommand,
    StoreEvidenceUploadCommand,
)
from hamoon.domains.evidence.application.handlers import (
    FinalizeEvidenceHandler,
    InitEvidenceUploadHandler,
    IssueEvidenceDownloadHandler,
    StoreEvidenceUploadHandler,
)
from hamoon.domains.evidence.domain.entities import (
    Evidence,
    EvidenceLifecycleStatus,
    EvidenceSensitivity,
)
from hamoon.domains.evidence.domain.errors import EvidenceError, EvidenceNotFoundError
from hamoon.domains.evidence.infrastructure.local_storage import (
    EvidenceCapabilitySigner,
    LocalEvidenceScanner,
    LocalEvidenceStorage,
)
from hamoon.domains.evidence.infrastructure.repositories import (
    SqlAlchemyEvidenceRepository,
)
from hamoon.domains.evidence.infrastructure.s3_storage import (
    S3CompatibleEvidenceStorage,
)
from hamoon.domains.evidence.ports.repositories import EvidenceStorage
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import get_db_session
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder

router = APIRouter(tags=["evidence"])


def _data(evidence: Evidence) -> EvidenceData:
    return EvidenceData(
        id=evidence.id,
        household_id=evidence.household_id,
        evidence_type=evidence.evidence_type,
        title=evidence.title,
        media_type=evidence.media_type,
        expected_size_bytes=evidence.expected_size_bytes,
        size_bytes=evidence.size_bytes,
        sha256=evidence.sha256,
        sensitivity_class=evidence.sensitivity_class,
        scan_status=evidence.scan_status,
        lifecycle_status=evidence.lifecycle_status,
        version=evidence.version,
        recorded_at=evidence.recorded_at,
        finalized_at=evidence.finalized_at,
    )


def _allowed_media_types(settings: Settings) -> frozenset[str]:
    return frozenset(
        value.strip().lower()
        for value in settings.evidence_allowed_media_types.split(",")
        if value.strip()
    )


def _storage(settings: Settings) -> EvidenceStorage:
    backend = settings.evidence_storage_backend.strip().lower()
    if backend == "local":
        return LocalEvidenceStorage(Path(settings.evidence_local_root))
    if backend == "s3":
        return S3CompatibleEvidenceStorage(
            endpoint=settings.evidence_s3_endpoint,
            access_key=settings.evidence_s3_access_key,
            secret_key=settings.evidence_s3_secret_key,
            bucket=settings.evidence_s3_bucket,
            region=settings.evidence_s3_region,
            timeout_seconds=settings.evidence_s3_request_timeout_seconds,
        )
    raise ValueError("EVIDENCE_STORAGE_BACKEND_INVALID")


def _storage_provider(settings: Settings) -> str:
    backend = settings.evidence_storage_backend.strip().lower()
    if backend == "local":
        return "LOCAL_PRIVATE"
    if backend == "s3":
        return "S3_COMPATIBLE_PRIVATE"
    raise ValueError("EVIDENCE_STORAGE_BACKEND_INVALID")


def _signer(settings: Settings) -> EvidenceCapabilitySigner:
    return EvidenceCapabilitySigner(settings.evidence_signing_secret)


def _ensure_sensitivity_access(
    *,
    context: AuthorizationContext,
    sensitivity: EvidenceSensitivity,
) -> None:
    if (
        sensitivity is EvidenceSensitivity.HIGHLY_SENSITIVE
        and "evidence.highly_sensitive" not in context.scopes
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )


def _raise_evidence_http(exc: Exception) -> NoReturn:
    code = str(exc)
    if isinstance(exc, EvidenceNotFoundError) or code in {
        "EVIDENCE_NOT_FOUND",
        "EVIDENCE_UPLOAD_SESSION_NOT_FOUND",
        "EVIDENCE_OBJECT_NOT_FOUND",
    }:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": code},
        ) from exc
    if code in {
        "EVIDENCE_UPLOAD_TOKEN_INVALID",
        "EVIDENCE_CAPABILITY_INVALID",
        "EVIDENCE_CAPABILITY_PURPOSE_MISMATCH",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": code},
        ) from exc
    if code in {"UPLOAD_SESSION_EXPIRED", "EVIDENCE_CAPABILITY_EXPIRED"}:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"code": code},
        ) from exc
    if code in {
        "EVIDENCE_VERSION_CONFLICT",
        "EVIDENCE_UPLOAD_SESSION_ALREADY_USED",
        "EVIDENCE_OBJECT_ALREADY_EXISTS",
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": code},
        ) from exc
    if code in {
        "EVIDENCE_STORAGE_UNAVAILABLE",
        "EVIDENCE_STORAGE_METADATA_INVALID",
    }:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": code},
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"code": code},
    ) from exc


@router.post(
    "/api/v1/households/{household_id}/evidence/uploads",
    response_model=InitEvidenceUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def init_evidence_upload(
    household_id: UUID,
    body: InitEvidenceUploadRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER, Role.MANAGER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InitEvidenceUploadResponse:
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    try:
        async with session.begin():
            await require_household_assignment(
                session=session,
                context=context,
                household_id=household_id,
            )
            _ensure_sensitivity_access(
                context=context,
                sensitivity=body.sensitivity_class,
            )
            result = await InitEvidenceUploadHandler(
                repository=SqlAlchemyEvidenceRepository(session),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
                environment=settings.environment,
                allowed_media_types=_allowed_media_types(settings),
                max_upload_bytes=settings.evidence_max_upload_bytes,
                upload_ttl_seconds=settings.evidence_upload_ttl_seconds,
                storage_provider=_storage_provider(settings),
            ).handle(
                InitEvidenceUploadCommand(
                    household_id=household_id,
                    evidence_type=body.evidence_type,
                    title=body.title,
                    description=body.description,
                    original_filename=body.original_filename,
                    media_type=body.media_type,
                    size_bytes=body.size_bytes,
                    sensitivity_class=body.sensitivity_class,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except (EvidenceError, ValueError) as exc:
        _raise_evidence_http(exc)

    upload_url = (
        f"/api/v1/evidence/uploads/{result.upload_session.id}/content"
        f"?token={result.upload_token}"
    )
    return InitEvidenceUploadResponse(
        data=InitEvidenceUploadData(
            evidence=_data(result.evidence),
            upload_session_id=result.upload_session.id,
            upload_url=upload_url,
            expires_at=result.upload_session.expires_at,
        )
    )


@router.put(
    "/api/v1/evidence/uploads/{session_id}/content",
    response_model=EvidenceResponse,
)
async def store_evidence_upload(
    session_id: UUID,
    request: Request,
    token: Annotated[str, Query(min_length=16)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EvidenceResponse:
    raw_length = request.headers.get("content-length")
    if raw_length is not None:
        try:
            declared_length = int(raw_length)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "CONTENT_LENGTH_INVALID"},
            ) from exc
        if declared_length > settings.evidence_max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={"code": "EVIDENCE_SIZE_REJECTED"},
            )
    content = await request.body()
    if len(content) > settings.evidence_max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "EVIDENCE_SIZE_REJECTED"},
        )
    correlation_id = current_correlation_id() or current_request_id() or "upload"
    try:
        async with session.begin():
            evidence = await StoreEvidenceUploadHandler(
                repository=SqlAlchemyEvidenceRepository(session),
                storage=_storage(settings),
                events=SqlAlchemyDomainEventRecorder(session),
            ).handle(
                StoreEvidenceUploadCommand(
                    session_id=session_id,
                    token=token,
                    content=content,
                    correlation_id=correlation_id,
                )
            )
    except (EvidenceError, EvidenceNotFoundError, ValueError) as exc:
        _raise_evidence_http(exc)
    return EvidenceResponse(data=_data(evidence))


@router.post(
    "/api/v1/evidence/{evidence_id}/finalize",
    response_model=EvidenceResponse,
)
async def finalize_evidence(
    evidence_id: UUID,
    body: FinalizeEvidenceRequest,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER, Role.MANAGER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EvidenceResponse:
    repository = SqlAlchemyEvidenceRepository(session)
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    try:
        async with session.begin():
            evidence = await repository.get(evidence_id)
            if evidence is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "RESOURCE_NOT_FOUND"},
                )
            await require_household_assignment(
                session=session,
                context=context,
                household_id=evidence.household_id,
            )
            _ensure_sensitivity_access(
                context=context,
                sensitivity=evidence.sensitivity_class,
            )
            updated = await FinalizeEvidenceHandler(
                repository=repository,
                storage=_storage(settings),
                scanner=LocalEvidenceScanner(),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                FinalizeEvidenceCommand(
                    evidence_id=evidence_id,
                    expected_sha256=body.expected_sha256,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except (EvidenceError, EvidenceNotFoundError, ValueError) as exc:
        _raise_evidence_http(exc)
    return EvidenceResponse(data=_data(updated))


@router.get(
    "/api/v1/evidence/{evidence_id}/download",
    response_model=EvidenceDownloadResponse,
)
async def issue_evidence_download(
    evidence_id: UUID,
    context: Annotated[
        AuthorizationContext,
        Depends(require_roles(Role.CASEWORKER, Role.MANAGER)),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EvidenceDownloadResponse:
    repository = SqlAlchemyEvidenceRepository(session)
    request_id = current_request_id() or "unknown"
    correlation_id = current_correlation_id() or request_id
    try:
        async with session.begin():
            evidence = await repository.get(evidence_id)
            if evidence is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "RESOURCE_NOT_FOUND"},
                )
            await require_household_assignment(
                session=session,
                context=context,
                household_id=evidence.household_id,
            )
            _ensure_sensitivity_access(
                context=context,
                sensitivity=evidence.sensitivity_class,
            )
            evidence, target = await IssueEvidenceDownloadHandler(
                repository=repository,
                signer=_signer(settings),
                audits=SqlAlchemyAuditRecorder(session),
                download_ttl_seconds=settings.evidence_download_ttl_seconds,
            ).handle(
                IssueEvidenceDownloadCommand(
                    evidence_id=evidence_id,
                    actor_id=context.actor_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
            )
    except (EvidenceError, EvidenceNotFoundError, ValueError) as exc:
        _raise_evidence_http(exc)
    return EvidenceDownloadResponse(
        data=EvidenceDownloadData(
            evidence_id=evidence.id,
            download_url=(
                f"/api/v1/evidence/{evidence.id}/content?token={target.token}"
            ),
            expires_at=target.expires_at,
            media_type=evidence.media_type,
        )
    )


@router.get("/api/v1/evidence/{evidence_id}/content")
async def read_evidence_content(
    evidence_id: UUID,
    token: Annotated[str, Query(min_length=16)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    try:
        capability = _signer(settings).verify(
            token=token,
            purpose="download",
        )
    except ValueError as exc:
        _raise_evidence_http(exc)
    if capability.evidence_id != evidence_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "EVIDENCE_CAPABILITY_RESOURCE_MISMATCH"},
        )
    evidence = await SqlAlchemyEvidenceRepository(session).get(evidence_id)
    if (
        evidence is None
        or evidence.lifecycle_status is not EvidenceLifecycleStatus.AVAILABLE
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
    try:
        content = await _storage(settings).read(storage_key=evidence.storage_key)
    except LookupError as exc:
        _raise_evidence_http(exc)
    return Response(
        content=content,
        media_type=evidence.media_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": "attachment",
        },
    )
