from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.evidence.domain.entities import Evidence, EvidenceUploadSession
from hamoon.domains.evidence.infrastructure.models import (
    EvidenceModel,
    EvidenceUploadSessionModel,
)


def _evidence(model: EvidenceModel) -> Evidence:
    return Evidence(
        id=model.id,
        household_id=model.household_id,
        evidence_type=model.evidence_type,
        title=model.title,
        description=model.description,
        storage_provider=model.storage_provider,
        storage_key=model.storage_key,
        original_filename=model.original_filename,
        media_type=model.media_type,
        expected_size_bytes=model.expected_size_bytes,
        size_bytes=model.size_bytes,
        sha256=model.sha256,
        sensitivity_class=model.sensitivity_class,
        scan_status=model.scan_status,
        lifecycle_status=model.lifecycle_status,
        schema_version=model.schema_version,
        version=model.version,
        recorded_at=model.recorded_at,
        recorded_by=model.recorded_by,
        finalized_at=model.finalized_at,
        scan_detail=model.scan_detail,
    )


def _upload_session(model: EvidenceUploadSessionModel) -> EvidenceUploadSession:
    return EvidenceUploadSession(
        id=model.id,
        evidence_id=model.evidence_id,
        token_hash=model.token_hash,
        expires_at=model.expires_at,
        created_at=model.created_at,
        used_at=model.used_at,
    )


class SqlAlchemyEvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        evidence: Evidence,
        upload_session: EvidenceUploadSession,
    ) -> None:
        self._session.add(
            EvidenceModel(
                id=evidence.id,
                household_id=evidence.household_id,
                evidence_type=evidence.evidence_type,
                title=evidence.title,
                description=evidence.description,
                storage_provider=evidence.storage_provider,
                storage_key=evidence.storage_key,
                original_filename=evidence.original_filename,
                media_type=evidence.media_type,
                expected_size_bytes=evidence.expected_size_bytes,
                size_bytes=evidence.size_bytes,
                sha256=evidence.sha256,
                sensitivity_class=evidence.sensitivity_class,
                scan_status=evidence.scan_status,
                lifecycle_status=evidence.lifecycle_status,
                schema_version=evidence.schema_version,
                version=evidence.version,
                recorded_at=evidence.recorded_at,
                recorded_by=evidence.recorded_by,
                finalized_at=evidence.finalized_at,
                scan_detail=evidence.scan_detail,
            )
        )
        self._session.add(
            EvidenceUploadSessionModel(
                id=upload_session.id,
                evidence_id=upload_session.evidence_id,
                token_hash=upload_session.token_hash,
                expires_at=upload_session.expires_at,
                created_at=upload_session.created_at,
                used_at=upload_session.used_at,
            )
        )

    async def get(self, evidence_id: UUID) -> Evidence | None:
        model = await self._session.get(EvidenceModel, evidence_id)
        return None if model is None else _evidence(model)

    async def save(
        self,
        evidence: Evidence,
        *,
        expected_version: int,
    ) -> None:
        result = await self._session.execute(
            select(EvidenceModel)
            .where(
                EvidenceModel.id == evidence.id,
                EvidenceModel.version == expected_version,
            )
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError("EVIDENCE_VERSION_CONFLICT")
        model.size_bytes = evidence.size_bytes
        model.sha256 = evidence.sha256
        model.scan_status = evidence.scan_status
        model.lifecycle_status = evidence.lifecycle_status
        model.version = evidence.version
        model.finalized_at = evidence.finalized_at
        model.scan_detail = evidence.scan_detail

    async def get_upload_session(
        self,
        session_id: UUID,
    ) -> EvidenceUploadSession | None:
        model = await self._session.get(EvidenceUploadSessionModel, session_id)
        return None if model is None else _upload_session(model)

    async def mark_upload_session_used(
        self,
        *,
        session_id: UUID,
        used_at: datetime,
    ) -> None:
        result = await self._session.execute(
            select(EvidenceUploadSessionModel)
            .where(EvidenceUploadSessionModel.id == session_id)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise LookupError("EVIDENCE_UPLOAD_SESSION_NOT_FOUND")
        if model.used_at is not None:
            raise ValueError("EVIDENCE_UPLOAD_SESSION_ALREADY_USED")
        model.used_at = used_at
