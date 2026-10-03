from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from hamoon.domains.evidence.domain.entities import Evidence, EvidenceUploadSession


@dataclass(frozen=True, slots=True)
class StoredEvidenceObject:
    size_bytes: int
    sha256: str


class EvidenceRepository(Protocol):
    async def add(
        self,
        evidence: Evidence,
        upload_session: EvidenceUploadSession,
    ) -> None: ...

    async def get(self, evidence_id: UUID) -> Evidence | None: ...

    async def save(
        self,
        evidence: Evidence,
        *,
        expected_version: int,
    ) -> None: ...

    async def get_upload_session(
        self,
        session_id: UUID,
    ) -> EvidenceUploadSession | None: ...

    async def mark_upload_session_used(
        self,
        *,
        session_id: UUID,
        used_at: datetime,
    ) -> None: ...


class EvidenceStorage(Protocol):
    async def put(
        self,
        *,
        storage_key: str,
        content: bytes,
    ) -> StoredEvidenceObject: ...

    async def metadata(
        self,
        *,
        storage_key: str,
    ) -> StoredEvidenceObject | None: ...

    async def read(
        self,
        *,
        storage_key: str,
    ) -> bytes: ...


class EvidenceScanner(Protocol):
    async def scan(
        self,
        *,
        media_type: str,
        content: bytes,
    ) -> tuple[bool, str | None]: ...
