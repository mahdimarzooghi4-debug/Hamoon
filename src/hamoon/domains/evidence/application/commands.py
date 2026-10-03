from dataclasses import dataclass
from uuid import UUID

from hamoon.domains.evidence.domain.entities import EvidenceSensitivity, EvidenceType


@dataclass(frozen=True, slots=True)
class InitEvidenceUploadCommand:
    household_id: UUID
    evidence_type: EvidenceType
    title: str
    description: str | None
    original_filename: str | None
    media_type: str
    size_bytes: int
    sensitivity_class: EvidenceSensitivity
    actor_id: UUID
    request_id: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class StoreEvidenceUploadCommand:
    session_id: UUID
    token: str
    content: bytes
    correlation_id: str


@dataclass(frozen=True, slots=True)
class FinalizeEvidenceCommand:
    evidence_id: UUID
    expected_sha256: str
    actor_id: UUID
    request_id: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class IssueEvidenceDownloadCommand:
    evidence_id: UUID
    actor_id: UUID
    request_id: str
    correlation_id: str
