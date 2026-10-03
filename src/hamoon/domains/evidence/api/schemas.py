from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from hamoon.domains.evidence.domain.entities import (
    EvidenceLifecycleStatus,
    EvidenceScanStatus,
    EvidenceSensitivity,
    EvidenceType,
)


class InitEvidenceUploadRequest(BaseModel):
    evidence_type: EvidenceType
    title: str = Field(min_length=1, max_length=250)
    description: str | None = Field(default=None, max_length=2000)
    original_filename: str | None = Field(default=None, max_length=255)
    media_type: str = Field(min_length=1, max_length=150)
    size_bytes: int = Field(gt=0)
    sensitivity_class: EvidenceSensitivity


class EvidenceData(BaseModel):
    id: UUID
    household_id: UUID
    evidence_type: EvidenceType
    title: str
    media_type: str
    expected_size_bytes: int
    size_bytes: int | None
    sha256: str | None
    sensitivity_class: EvidenceSensitivity
    scan_status: EvidenceScanStatus
    lifecycle_status: EvidenceLifecycleStatus
    version: int
    recorded_at: datetime
    finalized_at: datetime | None


class InitEvidenceUploadData(BaseModel):
    evidence: EvidenceData
    upload_session_id: UUID
    upload_url: str
    expires_at: datetime


class InitEvidenceUploadResponse(BaseModel):
    data: InitEvidenceUploadData


class EvidenceResponse(BaseModel):
    data: EvidenceData


class FinalizeEvidenceRequest(BaseModel):
    expected_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
    )


class EvidenceDownloadData(BaseModel):
    evidence_id: UUID
    download_url: str
    expires_at: datetime
    media_type: str


class EvidenceDownloadResponse(BaseModel):
    data: EvidenceDownloadData
