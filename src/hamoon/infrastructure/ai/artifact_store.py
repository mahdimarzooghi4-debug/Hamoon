from __future__ import annotations

import hashlib
import re
from pathlib import Path

from hamoon.app.config.settings import Settings
from hamoon.domains.evidence.infrastructure.local_storage import LocalEvidenceStorage
from hamoon.domains.evidence.infrastructure.s3_storage import S3CompatibleEvidenceStorage
from hamoon.domains.evidence.ports.repositories import EvidenceStorage
from hamoon.infrastructure.ai.internal_model import StoredInternalModelArtifact


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class InternalModelArtifactStoreError(RuntimeError):
    """Immutable internal-model artifact storage failed closed."""


class ObjectStorageInternalModelArtifactStore:
    def __init__(self, storage: EvidenceStorage) -> None:
        self._storage = storage

    @staticmethod
    def _key(artifact_sha256: str) -> str:
        digest = artifact_sha256.strip().lower()
        if _SHA256_RE.fullmatch(digest) is None:
            raise InternalModelArtifactStoreError(
                "INTERNAL_MODEL_ARTIFACT_DIGEST_INVALID"
            )
        return f"internal-model-artifacts/sha256/{digest}"

    async def put(
        self,
        *,
        artifact_sha256: str,
        content: bytes,
    ) -> StoredInternalModelArtifact:
        digest = artifact_sha256.strip().lower()
        actual = hashlib.sha256(content).hexdigest()
        if digest != actual:
            raise InternalModelArtifactStoreError(
                "INTERNAL_MODEL_ARTIFACT_DIGEST_MISMATCH"
            )
        key = self._key(digest)

        existing = await self._storage.metadata(storage_key=key)
        if existing is not None:
            if (
                existing.sha256.lower() != digest
                or existing.size_bytes != len(content)
            ):
                raise InternalModelArtifactStoreError(
                    "INTERNAL_MODEL_ARTIFACT_IMMUTABILITY_CONFLICT"
                )
            return StoredInternalModelArtifact(
                artifact_sha256=digest,
                size_bytes=existing.size_bytes,
            )

        try:
            stored = await self._storage.put(
                storage_key=key,
                content=content,
            )
        except ValueError as exc:
            if str(exc) != "EVIDENCE_OBJECT_ALREADY_EXISTS":
                raise InternalModelArtifactStoreError(
                    "INTERNAL_MODEL_ARTIFACT_STORAGE_UNAVAILABLE"
                ) from exc
            existing = await self._storage.metadata(storage_key=key)
            if existing is None:
                raise InternalModelArtifactStoreError(
                    "INTERNAL_MODEL_ARTIFACT_STORAGE_RACE"
                ) from exc
            stored = existing

        if stored.sha256.lower() != digest or stored.size_bytes != len(content):
            raise InternalModelArtifactStoreError(
                "INTERNAL_MODEL_ARTIFACT_STORE_ATTESTATION_MISMATCH"
            )
        return StoredInternalModelArtifact(
            artifact_sha256=digest,
            size_bytes=stored.size_bytes,
        )

    async def read(
        self,
        *,
        artifact_sha256: str,
    ) -> bytes:
        digest = artifact_sha256.strip().lower()
        key = self._key(digest)
        try:
            content = await self._storage.read(storage_key=key)
        except (LookupError, ValueError) as exc:
            raise InternalModelArtifactStoreError(
                "INTERNAL_MODEL_ARTIFACT_NOT_AVAILABLE"
            ) from exc
        if hashlib.sha256(content).hexdigest() != digest:
            raise InternalModelArtifactStoreError(
                "INTERNAL_MODEL_ARTIFACT_DIGEST_MISMATCH"
            )
        return content


def build_internal_model_artifact_store(
    settings: Settings,
) -> ObjectStorageInternalModelArtifactStore:
    backend = settings.internal_model_artifact_storage_backend.strip().lower()
    if backend == "local":
        storage: EvidenceStorage = LocalEvidenceStorage(
            Path(settings.internal_model_artifact_local_root)
        )
    elif backend == "s3":
        storage = S3CompatibleEvidenceStorage(
            endpoint=settings.internal_model_artifact_s3_endpoint,
            access_key=settings.internal_model_artifact_s3_access_key,
            secret_key=settings.internal_model_artifact_s3_secret_key,
            bucket=settings.internal_model_artifact_s3_bucket,
            region=settings.internal_model_artifact_s3_region,
            timeout_seconds=(
                settings.internal_model_artifact_s3_request_timeout_seconds
            ),
        )
    else:
        raise InternalModelArtifactStoreError(
            "INTERNAL_MODEL_ARTIFACT_STORAGE_BACKEND_INVALID"
        )
    return ObjectStorageInternalModelArtifactStore(storage)
