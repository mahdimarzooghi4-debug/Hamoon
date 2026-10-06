from pathlib import Path

import pytest

from hamoon.domains.evidence.infrastructure.local_storage import LocalEvidenceStorage
from hamoon.infrastructure.ai.artifact_store import (
    InternalModelArtifactStoreError,
    ObjectStorageInternalModelArtifactStore,
)


@pytest.mark.asyncio
async def test_internal_model_artifact_store_is_digest_addressed_and_idempotent(
    tmp_path: Path,
) -> None:
    store = ObjectStorageInternalModelArtifactStore(
        LocalEvidenceStorage(tmp_path)
    )
    content = b"internal-model-artifact"
    import hashlib

    digest = hashlib.sha256(content).hexdigest()

    first = await store.put(
        artifact_sha256=digest,
        content=content,
    )
    second = await store.put(
        artifact_sha256=digest,
        content=content,
    )

    assert first == second
    assert await store.read(artifact_sha256=digest) == content
    assert (
        tmp_path
        / "internal-model-artifacts"
        / "sha256"
        / digest
    ).read_bytes() == content


@pytest.mark.asyncio
async def test_internal_model_artifact_store_rejects_digest_mismatch(
    tmp_path: Path,
) -> None:
    store = ObjectStorageInternalModelArtifactStore(
        LocalEvidenceStorage(tmp_path)
    )

    with pytest.raises(
        InternalModelArtifactStoreError,
        match="INTERNAL_MODEL_ARTIFACT_DIGEST_MISMATCH",
    ):
        await store.put(
            artifact_sha256="a" * 64,
            content=b"different-content",
        )
