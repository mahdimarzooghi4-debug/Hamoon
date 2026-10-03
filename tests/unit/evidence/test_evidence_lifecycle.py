from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest

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
    EvidenceLifecycleStatus,
    EvidenceScanStatus,
    EvidenceSensitivity,
    EvidenceType,
)
from hamoon.domains.evidence.domain.errors import EvidenceError
from hamoon.domains.evidence.infrastructure.local_storage import (
    EvidenceCapabilitySigner,
    LocalEvidenceScanner,
    LocalEvidenceStorage,
)

ACTOR = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD = UUID("22222222-2222-2222-2222-222222222222")


class Recorder:
    def __init__(self) -> None:
        self.items = []

    async def record(self, item) -> None:
        self.items.append(item)


class Repository:
    def __init__(self) -> None:
        self.evidence = None
        self.upload_session = None

    async def add(self, evidence, upload_session) -> None:
        self.evidence = evidence
        self.upload_session = upload_session

    async def get(self, evidence_id):
        if self.evidence is not None and self.evidence.id == evidence_id:
            return self.evidence
        return None

    async def save(self, evidence, *, expected_version: int) -> None:
        assert self.evidence is not None
        assert self.evidence.version == expected_version
        self.evidence = evidence

    async def get_upload_session(self, session_id):
        if self.upload_session is not None and self.upload_session.id == session_id:
            return self.upload_session
        return None

    async def mark_upload_session_used(self, *, session_id, used_at) -> None:
        assert self.upload_session is not None
        assert self.upload_session.id == session_id
        assert self.upload_session.used_at is None
        self.upload_session = replace(self.upload_session, used_at=used_at)


async def _init(repo: Repository, events: Recorder, audits: Recorder, size: int):
    return await InitEvidenceUploadHandler(
        repository=repo,
        events=events,
        audits=audits,
        environment="test",
        allowed_media_types=frozenset({"application/pdf", "image/png"}),
        max_upload_bytes=1024 * 1024,
        upload_ttl_seconds=300,
    ).handle(
        InitEvidenceUploadCommand(
            household_id=HOUSEHOLD,
            evidence_type=EvidenceType.DOCUMENT,
            title="Assessment report",
            description=None,
            original_filename="report.pdf",
            media_type="application/pdf",
            size_bytes=size,
            sensitivity_class=EvidenceSensitivity.SENSITIVE_PERSONAL,
            actor_id=ACTOR,
            request_id="req-1",
            correlation_id="corr-1",
        )
    )


@pytest.mark.asyncio
async def test_private_evidence_happy_path_is_hash_verified_and_downloadable(
    tmp_path: Path,
) -> None:
    repo = Repository()
    events = Recorder()
    audits = Recorder()
    content = b"%PDF-1.7\nsynthetic test evidence\n"
    initialized = await _init(repo, events, audits, len(content))
    storage = LocalEvidenceStorage(tmp_path)

    uploaded = await StoreEvidenceUploadHandler(
        repository=repo,
        storage=storage,
        events=events,
    ).handle(
        StoreEvidenceUploadCommand(
            session_id=initialized.upload_session.id,
            token=initialized.upload_token,
            content=content,
            correlation_id="corr-1",
        )
    )
    assert uploaded.lifecycle_status is EvidenceLifecycleStatus.UPLOADED

    finalized = await FinalizeEvidenceHandler(
        repository=repo,
        storage=storage,
        scanner=LocalEvidenceScanner(),
        events=events,
        audits=audits,
    ).handle(
        FinalizeEvidenceCommand(
            evidence_id=uploaded.id,
            expected_sha256=sha256(content).hexdigest(),
            actor_id=ACTOR,
            request_id="req-2",
            correlation_id="corr-1",
        )
    )
    assert finalized.lifecycle_status is EvidenceLifecycleStatus.AVAILABLE
    assert finalized.scan_status is EvidenceScanStatus.CLEAN
    assert finalized.sha256 == sha256(content).hexdigest()

    signer = EvidenceCapabilitySigner("a-strong-test-secret")
    evidence, target = await IssueEvidenceDownloadHandler(
        repository=repo,
        signer=signer,
        audits=audits,
        download_ttl_seconds=60,
    ).handle(
        IssueEvidenceDownloadCommand(
            evidence_id=finalized.id,
            actor_id=ACTOR,
            request_id="req-3",
            correlation_id="corr-1",
        )
    )
    capability = signer.verify(token=target.token, purpose="download")
    assert capability.evidence_id == evidence.id
    assert await storage.read(storage_key=evidence.storage_key) == content

    event_types = [item.event_type for item in events.items]
    assert event_types == [
        "EvidenceUploadInitiated",
        "EvidenceUploaded",
        "EvidenceAvailable",
    ]


@pytest.mark.asyncio
async def test_finalize_rejects_hash_mismatch(tmp_path: Path) -> None:
    repo = Repository()
    events = Recorder()
    audits = Recorder()
    content = b"%PDF-1.7\nhash mismatch\n"
    initialized = await _init(repo, events, audits, len(content))
    storage = LocalEvidenceStorage(tmp_path)
    uploaded = await StoreEvidenceUploadHandler(
        repository=repo,
        storage=storage,
        events=events,
    ).handle(
        StoreEvidenceUploadCommand(
            session_id=initialized.upload_session.id,
            token=initialized.upload_token,
            content=content,
            correlation_id="corr",
        )
    )

    with pytest.raises(EvidenceError, match="HASH_MISMATCH"):
        await FinalizeEvidenceHandler(
            repository=repo,
            storage=storage,
            scanner=LocalEvidenceScanner(),
            events=events,
            audits=audits,
        ).handle(
            FinalizeEvidenceCommand(
                evidence_id=uploaded.id,
                expected_sha256="0" * 64,
                actor_id=ACTOR,
                request_id="req",
                correlation_id="corr",
            )
        )
    assert repo.evidence.lifecycle_status is EvidenceLifecycleStatus.UPLOADED


@pytest.mark.asyncio
async def test_media_signature_mismatch_is_quarantined(tmp_path: Path) -> None:
    repo = Repository()
    events = Recorder()
    audits = Recorder()
    content = b"not actually a PDF"
    initialized = await _init(repo, events, audits, len(content))
    storage = LocalEvidenceStorage(tmp_path)
    uploaded = await StoreEvidenceUploadHandler(
        repository=repo,
        storage=storage,
        events=events,
    ).handle(
        StoreEvidenceUploadCommand(
            session_id=initialized.upload_session.id,
            token=initialized.upload_token,
            content=content,
            correlation_id="corr",
        )
    )
    finalized = await FinalizeEvidenceHandler(
        repository=repo,
        storage=storage,
        scanner=LocalEvidenceScanner(),
        events=events,
        audits=audits,
    ).handle(
        FinalizeEvidenceCommand(
            evidence_id=uploaded.id,
            expected_sha256=sha256(content).hexdigest(),
            actor_id=ACTOR,
            request_id="req",
            correlation_id="corr",
        )
    )
    assert finalized.lifecycle_status is EvidenceLifecycleStatus.QUARANTINED
    assert finalized.scan_status is EvidenceScanStatus.INFECTED
    assert finalized.scan_detail == "MEDIA_SIGNATURE_MISMATCH"


@pytest.mark.asyncio
async def test_upload_capability_is_one_time(tmp_path: Path) -> None:
    repo = Repository()
    events = Recorder()
    audits = Recorder()
    content = b"%PDF-1.7\none time\n"
    initialized = await _init(repo, events, audits, len(content))
    handler = StoreEvidenceUploadHandler(
        repository=repo,
        storage=LocalEvidenceStorage(tmp_path),
        events=events,
    )
    command = StoreEvidenceUploadCommand(
        session_id=initialized.upload_session.id,
        token=initialized.upload_token,
        content=content,
        correlation_id="corr",
    )
    await handler.handle(command)
    with pytest.raises(EvidenceError, match="EVIDENCE_UPLOAD_SESSION_ALREADY_USED"):
        await handler.handle(command)
