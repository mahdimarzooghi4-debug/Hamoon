from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from hamoon.domains.evidence.application.commands import (
    FinalizeEvidenceCommand,
    InitEvidenceUploadCommand,
    IssueEvidenceDownloadCommand,
    StoreEvidenceUploadCommand,
)
from hamoon.domains.evidence.domain.entities import (
    Evidence,
    EvidenceLifecycleStatus,
    EvidenceScanStatus,
    EvidenceUploadSession,
)
from hamoon.domains.evidence.domain.errors import EvidenceError, EvidenceNotFoundError
from hamoon.domains.evidence.infrastructure.local_storage import EvidenceCapabilitySigner
from hamoon.domains.evidence.ports.repositories import (
    EvidenceRepository,
    EvidenceScanner,
    EvidenceStorage,
)
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder


@dataclass(frozen=True, slots=True)
class InitEvidenceUploadResult:
    evidence: Evidence
    upload_session: EvidenceUploadSession
    upload_token: str


@dataclass(frozen=True, slots=True)
class EvidenceDownloadTarget:
    token: str
    expires_at: datetime


class InitEvidenceUploadHandler:
    def __init__(
        self,
        *,
        repository: EvidenceRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
        environment: str,
        allowed_media_types: frozenset[str],
        max_upload_bytes: int,
        upload_ttl_seconds: int,
    ) -> None:
        self._repository = repository
        self._events = events
        self._audits = audits
        self._environment = environment
        self._allowed_media_types = allowed_media_types
        self._max_upload_bytes = max_upload_bytes
        self._upload_ttl_seconds = upload_ttl_seconds

    async def handle(
        self,
        command: InitEvidenceUploadCommand,
    ) -> InitEvidenceUploadResult:
        title = command.title.strip()
        media_type = command.media_type.strip().lower()
        if not title:
            raise EvidenceError("EVIDENCE_TITLE_REQUIRED")
        if media_type not in self._allowed_media_types:
            raise EvidenceError("MEDIA_TYPE_REJECTED")
        if command.size_bytes <= 0 or command.size_bytes > self._max_upload_bytes:
            raise EvidenceError("EVIDENCE_SIZE_REJECTED")

        now = datetime.now(UTC)
        evidence_id = uuid4()
        object_id = uuid4().hex
        storage_key = (
            f"evidence/{self._environment}/{now:%Y/%m}/"
            f"{evidence_id}/{object_id}"
        )
        raw_token = secrets.token_urlsafe(32)
        upload_session = EvidenceUploadSession(
            id=uuid4(),
            evidence_id=evidence_id,
            token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            expires_at=now + timedelta(seconds=self._upload_ttl_seconds),
            created_at=now,
        )
        evidence = Evidence(
            id=evidence_id,
            household_id=command.household_id,
            evidence_type=command.evidence_type,
            title=title,
            description=(
                command.description.strip()
                if command.description and command.description.strip()
                else None
            ),
            storage_provider="LOCAL_PRIVATE",
            storage_key=storage_key,
            original_filename=command.original_filename,
            media_type=media_type,
            expected_size_bytes=command.size_bytes,
            size_bytes=None,
            sha256=None,
            sensitivity_class=command.sensitivity_class,
            scan_status=EvidenceScanStatus.PENDING,
            lifecycle_status=EvidenceLifecycleStatus.PENDING_UPLOAD,
            schema_version="evidence-v1",
            version=1,
            recorded_at=now,
            recorded_by=command.actor_id,
        )
        await self._repository.add(evidence, upload_session)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="EvidenceUploadInitiated",
                event_version=1,
                aggregate_type="EVIDENCE",
                aggregate_id=evidence.id,
                aggregate_version=evidence.version,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "evidence_id": str(evidence.id),
                    "household_id": str(evidence.household_id),
                    "media_type": evidence.media_type,
                    "expected_size_bytes": evidence.expected_size_bytes,
                    "sensitivity_class": evidence.sensitivity_class.value,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="evidence.upload.init",
                resource_type="EVIDENCE",
                resource_id=evidence.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="HOUSEHOLD_EVIDENCE",
                metadata={
                    "event_id": str(event_id),
                    "media_type": evidence.media_type,
                    "size_bytes": evidence.expected_size_bytes,
                },
            )
        )
        return InitEvidenceUploadResult(
            evidence=evidence,
            upload_session=upload_session,
            upload_token=raw_token,
        )


class StoreEvidenceUploadHandler:
    def __init__(
        self,
        *,
        repository: EvidenceRepository,
        storage: EvidenceStorage,
        events: DomainEventRecorder,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._events = events

    async def handle(
        self,
        command: StoreEvidenceUploadCommand,
    ) -> Evidence:
        session = await self._repository.get_upload_session(command.session_id)
        if session is None:
            raise EvidenceNotFoundError("EVIDENCE_UPLOAD_SESSION_NOT_FOUND")
        if session.consumed:
            raise EvidenceError("EVIDENCE_UPLOAD_SESSION_ALREADY_USED")
        if session.expires_at <= datetime.now(UTC):
            raise EvidenceError("UPLOAD_SESSION_EXPIRED")
        actual_hash = hashlib.sha256(command.token.encode("utf-8")).hexdigest()
        if not secrets.compare_digest(actual_hash, session.token_hash):
            raise EvidenceError("EVIDENCE_UPLOAD_TOKEN_INVALID")

        evidence = await self._repository.get(session.evidence_id)
        if evidence is None:
            raise EvidenceNotFoundError("EVIDENCE_NOT_FOUND")
        if len(command.content) != evidence.expected_size_bytes:
            raise EvidenceError("OBJECT_SIZE_MISMATCH")

        stored = await self._storage.put(
            storage_key=evidence.storage_key,
            content=command.content,
        )
        updated = evidence.mark_uploaded(size_bytes=stored.size_bytes)
        now = datetime.now(UTC)
        await self._repository.save(updated, expected_version=evidence.version)
        await self._repository.mark_upload_session_used(
            session_id=session.id,
            used_at=now,
        )
        await self._events.record(
            DomainEventRecord(
                event_id=uuid4(),
                event_type="EvidenceUploaded",
                event_version=1,
                aggregate_type="EVIDENCE",
                aggregate_id=updated.id,
                aggregate_version=updated.version,
                actor_id=evidence.recorded_by,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "evidence_id": str(updated.id),
                    "household_id": str(updated.household_id),
                    "size_bytes": stored.size_bytes,
                },
            )
        )
        return updated


class FinalizeEvidenceHandler:
    def __init__(
        self,
        *,
        repository: EvidenceRepository,
        storage: EvidenceStorage,
        scanner: EvidenceScanner,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._scanner = scanner
        self._events = events
        self._audits = audits

    async def handle(
        self,
        command: FinalizeEvidenceCommand,
    ) -> Evidence:
        evidence = await self._repository.get(command.evidence_id)
        if evidence is None:
            raise EvidenceNotFoundError("EVIDENCE_NOT_FOUND")
        if evidence.lifecycle_status is not EvidenceLifecycleStatus.UPLOADED:
            raise EvidenceError("EVIDENCE_NOT_UPLOADED")

        metadata = await self._storage.metadata(storage_key=evidence.storage_key)
        if metadata is None:
            raise EvidenceError("OBJECT_NOT_FOUND")
        if metadata.size_bytes != evidence.expected_size_bytes:
            raise EvidenceError("OBJECT_SIZE_MISMATCH")
        if metadata.sha256 != command.expected_sha256.lower():
            raise EvidenceError("HASH_MISMATCH")

        content = await self._storage.read(storage_key=evidence.storage_key)
        clean, detail = await self._scanner.scan(
            media_type=evidence.media_type,
            content=content,
        )
        now = datetime.now(UTC)
        scan_status = (
            EvidenceScanStatus.CLEAN if clean else EvidenceScanStatus.INFECTED
        )
        updated = evidence.finalize(
            sha256=metadata.sha256,
            scan_status=scan_status,
            finalized_at=now,
            scan_detail=detail,
        )
        await self._repository.save(updated, expected_version=evidence.version)

        event_type = (
            "EvidenceAvailable"
            if updated.lifecycle_status is EvidenceLifecycleStatus.AVAILABLE
            else "EvidenceQuarantined"
        )
        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type=event_type,
                event_version=1,
                aggregate_type="EVIDENCE",
                aggregate_id=updated.id,
                aggregate_version=updated.version,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "evidence_id": str(updated.id),
                    "household_id": str(updated.household_id),
                    "sha256": updated.sha256,
                    "scan_status": updated.scan_status.value,
                    "lifecycle_status": updated.lifecycle_status.value,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="evidence.finalize",
                resource_type="EVIDENCE",
                resource_id=updated.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="HOUSEHOLD_EVIDENCE",
                metadata={
                    "event_id": str(event_id),
                    "sha256": updated.sha256 or "",
                    "scan_status": updated.scan_status.value,
                },
            )
        )
        return updated


class IssueEvidenceDownloadHandler:
    def __init__(
        self,
        *,
        repository: EvidenceRepository,
        signer: EvidenceCapabilitySigner,
        audits: AuditRecorder,
        download_ttl_seconds: int,
    ) -> None:
        self._repository = repository
        self._signer = signer
        self._audits = audits
        self._download_ttl_seconds = download_ttl_seconds

    async def handle(
        self,
        command: IssueEvidenceDownloadCommand,
    ) -> tuple[Evidence, EvidenceDownloadTarget]:
        evidence = await self._repository.get(command.evidence_id)
        if evidence is None:
            raise EvidenceNotFoundError("EVIDENCE_NOT_FOUND")
        if evidence.lifecycle_status is not EvidenceLifecycleStatus.AVAILABLE:
            raise EvidenceError("EVIDENCE_NOT_AVAILABLE")
        token, expires_at = self._signer.issue(
            evidence_id=evidence.id,
            purpose="download",
            ttl_seconds=self._download_ttl_seconds,
        )
        now = datetime.now(UTC)
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="evidence.download.issue",
                resource_type="EVIDENCE",
                resource_id=evidence.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="HOUSEHOLD_EVIDENCE",
                metadata={
                    "sensitivity_class": evidence.sensitivity_class.value,
                    "expires_at": expires_at.isoformat(),
                },
            )
        )
        return evidence, EvidenceDownloadTarget(
            token=token,
            expires_at=expires_at,
        )
