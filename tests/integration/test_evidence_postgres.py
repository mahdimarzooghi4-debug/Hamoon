from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from hamoon.app.config.settings import get_settings
from hamoon.domains.evidence.application.commands import (
    FinalizeEvidenceCommand,
    InitEvidenceUploadCommand,
    StoreEvidenceUploadCommand,
)
from hamoon.domains.evidence.application.handlers import (
    FinalizeEvidenceHandler,
    InitEvidenceUploadHandler,
    StoreEvidenceUploadHandler,
)
from hamoon.domains.evidence.domain.entities import (
    EvidenceLifecycleStatus,
    EvidenceSensitivity,
    EvidenceType,
)
from hamoon.domains.evidence.infrastructure.local_storage import LocalEvidenceScanner
from hamoon.domains.evidence.infrastructure.s3_storage import (
    S3CompatibleEvidenceStorage,
)
from hamoon.domains.evidence.infrastructure.repositories import (
    SqlAlchemyEvidenceRepository,
)
from hamoon.domains.household.domain.entities import HouseholdStatus
from hamoon.domains.household.infrastructure.models import HouseholdModel
from hamoon.domains.identity.domain.entities import ActorStatus, ActorType
from hamoon.domains.identity.infrastructure.models import ActorModel
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder


@pytest.mark.asyncio
async def test_evidence_lifecycle_persists_on_real_postgres_and_minio() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    actor_id = uuid4()
    household_id = uuid4()
    now = datetime.now(UTC)
    content = b"%PDF-1.7\npostgres integration evidence\n"
    digest = sha256(content).hexdigest()
    storage = S3CompatibleEvidenceStorage(
        endpoint=settings.evidence_s3_endpoint,
        access_key=settings.evidence_s3_access_key,
        secret_key=settings.evidence_s3_secret_key,
        bucket=settings.evidence_s3_bucket,
        region=settings.evidence_s3_region,
        timeout_seconds=settings.evidence_s3_request_timeout_seconds,
    )

    async with session_maker() as session:
        async with session.begin():
            session.add(
                ActorModel(
                    id=actor_id,
                    actor_type=ActorType.HUMAN,
                    display_name="Integration Actor",
                    status=ActorStatus.ACTIVE,
                    created_at=now,
                )
            )
            await session.flush()
            session.add(
                HouseholdModel(
                    id=household_id,
                    case_code=f"INT-{household_id.hex[:12]}",
                    lifecycle_status=HouseholdStatus.DRAFT,
                    organizational_unit_id="integration",
                    primary_caseworker_id=actor_id,
                    version=1,
                    created_at=now,
                    created_by=actor_id,
                    closed_at=None,
                )
            )

    async with session_maker() as session:
        repository = SqlAlchemyEvidenceRepository(session)
        async with session.begin():
            initialized = await InitEvidenceUploadHandler(
                repository=repository,
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
                environment="integration",
                allowed_media_types=frozenset({"application/pdf"}),
                max_upload_bytes=1024 * 1024,
                upload_ttl_seconds=300,
                storage_provider="S3_COMPATIBLE_PRIVATE",
            ).handle(
                InitEvidenceUploadCommand(
                    household_id=household_id,
                    evidence_type=EvidenceType.DOCUMENT,
                    title="Integration PDF",
                    description=None,
                    original_filename="integration.pdf",
                    media_type="application/pdf",
                    size_bytes=len(content),
                    sensitivity_class=EvidenceSensitivity.SENSITIVE_PERSONAL,
                    actor_id=actor_id,
                    request_id="integration-evidence-init",
                    correlation_id=f"evidence-{household_id}",
                )
            )

        async with session.begin():
            uploaded = await StoreEvidenceUploadHandler(
                repository=repository,
                storage=storage,
                events=SqlAlchemyDomainEventRecorder(session),
            ).handle(
                StoreEvidenceUploadCommand(
                    session_id=initialized.upload_session.id,
                    token=initialized.upload_token,
                    content=content,
                    correlation_id=f"evidence-{household_id}",
                )
            )
        assert uploaded.lifecycle_status is EvidenceLifecycleStatus.UPLOADED

        async with session.begin():
            finalized = await FinalizeEvidenceHandler(
                repository=repository,
                storage=storage,
                scanner=LocalEvidenceScanner(),
                events=SqlAlchemyDomainEventRecorder(session),
                audits=SqlAlchemyAuditRecorder(session),
            ).handle(
                FinalizeEvidenceCommand(
                    evidence_id=uploaded.id,
                    expected_sha256=digest,
                    actor_id=actor_id,
                    request_id="integration-evidence-finalize",
                    correlation_id=f"evidence-{household_id}",
                )
            )

        assert finalized.lifecycle_status is EvidenceLifecycleStatus.AVAILABLE
        assert finalized.sha256 == digest

    async with session_maker() as session:
        persisted = await SqlAlchemyEvidenceRepository(session).get(finalized.id)
        assert persisted is not None
        assert persisted.lifecycle_status is EvidenceLifecycleStatus.AVAILABLE
        assert persisted.sha256 == digest
        assert persisted.household_id == household_id
        assert persisted.storage_provider == "S3_COMPATIBLE_PRIVATE"
        assert await storage.read(storage_key=persisted.storage_key) == content

    await engine.dispose()
