from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class EvidenceType(StrEnum):
    DOCUMENT = "DOCUMENT"
    IMAGE = "IMAGE"
    PROVIDER_REPORT = "PROVIDER_REPORT"
    ASSESSMENT_ATTACHMENT = "ASSESSMENT_ATTACHMENT"
    OTHER = "OTHER"


class EvidenceSensitivity(StrEnum):
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    SENSITIVE_PERSONAL = "SENSITIVE_PERSONAL"
    HIGHLY_SENSITIVE = "HIGHLY_SENSITIVE"


class EvidenceScanStatus(StrEnum):
    PENDING = "PENDING"
    SCANNING = "SCANNING"
    CLEAN = "CLEAN"
    FAILED = "FAILED"
    INFECTED = "INFECTED"


class EvidenceLifecycleStatus(StrEnum):
    PENDING_UPLOAD = "PENDING_UPLOAD"
    UPLOADED = "UPLOADED"
    SCANNING = "SCANNING"
    AVAILABLE = "AVAILABLE"
    UPLOAD_FAILED = "UPLOAD_FAILED"
    SCAN_FAILED = "SCAN_FAILED"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True, slots=True)
class Evidence:
    id: UUID
    household_id: UUID
    evidence_type: EvidenceType
    title: str
    description: str | None
    storage_provider: str
    storage_key: str
    original_filename: str | None
    media_type: str
    expected_size_bytes: int
    size_bytes: int | None
    sha256: str | None
    sensitivity_class: EvidenceSensitivity
    scan_status: EvidenceScanStatus
    lifecycle_status: EvidenceLifecycleStatus
    schema_version: str
    version: int
    recorded_at: datetime
    recorded_by: UUID
    finalized_at: datetime | None = None
    scan_detail: str | None = None

    def mark_uploaded(
        self,
        *,
        size_bytes: int,
    ) -> "Evidence":
        if self.lifecycle_status is not EvidenceLifecycleStatus.PENDING_UPLOAD:
            raise ValueError("EVIDENCE_NOT_PENDING_UPLOAD")
        if size_bytes != self.expected_size_bytes:
            raise ValueError("OBJECT_SIZE_MISMATCH")
        return replace(
            self,
            size_bytes=size_bytes,
            lifecycle_status=EvidenceLifecycleStatus.UPLOADED,
            version=self.version + 1,
        )

    def finalize(
        self,
        *,
        sha256: str,
        scan_status: EvidenceScanStatus,
        finalized_at: datetime,
        scan_detail: str | None = None,
    ) -> "Evidence":
        if self.lifecycle_status is not EvidenceLifecycleStatus.UPLOADED:
            raise ValueError("EVIDENCE_NOT_UPLOADED")
        if scan_status is EvidenceScanStatus.CLEAN:
            lifecycle = EvidenceLifecycleStatus.AVAILABLE
        elif scan_status is EvidenceScanStatus.INFECTED:
            lifecycle = EvidenceLifecycleStatus.QUARANTINED
        else:
            lifecycle = EvidenceLifecycleStatus.SCAN_FAILED
        return replace(
            self,
            sha256=sha256,
            scan_status=scan_status,
            lifecycle_status=lifecycle,
            finalized_at=finalized_at,
            scan_detail=scan_detail,
            version=self.version + 1,
        )


@dataclass(frozen=True, slots=True)
class EvidenceUploadSession:
    id: UUID
    evidence_id: UUID
    token_hash: str
    expires_at: datetime
    created_at: datetime
    used_at: datetime | None = None

    @property
    def consumed(self) -> bool:
        return self.used_at is not None
