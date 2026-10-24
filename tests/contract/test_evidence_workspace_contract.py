from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from hamoon.domains.evidence.api import routes
from hamoon.domains.evidence.domain.entities import (
    Evidence,
    EvidenceLifecycleStatus,
    EvidenceScanStatus,
    EvidenceSensitivity,
    EvidenceType,
)
from hamoon.domains.evidence.infrastructure.repositories import SqlAlchemyEvidenceRepository


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _Session:
    def begin(self):
        return _Transaction()


def _evidence(household_id, sensitivity):
    now = datetime.now(UTC)
    return Evidence(
        id=uuid4(),
        household_id=household_id,
        evidence_type=EvidenceType.DOCUMENT,
        title=f"مدرک {sensitivity.value}",
        description=None,
        storage_provider="LOCAL_PRIVATE",
        storage_key=f"evidence/test/{uuid4().hex}",
        original_filename="document.pdf",
        media_type="application/pdf",
        expected_size_bytes=128,
        size_bytes=128,
        sha256="a" * 64,
        sensitivity_class=sensitivity,
        scan_status=EvidenceScanStatus.CLEAN,
        lifecycle_status=EvidenceLifecycleStatus.AVAILABLE,
        schema_version="evidence-v1",
        version=2,
        recorded_at=now,
        recorded_by=uuid4(),
        finalized_at=now,
    )


async def test_household_evidence_list_hides_highly_sensitive_without_scope(monkeypatch):
    household_id = uuid4()
    regular = _evidence(household_id, EvidenceSensitivity.INTERNAL)
    restricted = _evidence(household_id, EvidenceSensitivity.HIGHLY_SENSITIVE)

    class FakeRepository:
        include_highly_sensitive = None

        async def list_for_household(
            self,
            requested_household_id,
            *,
            limit,
            include_highly_sensitive,
        ):
            assert requested_household_id == household_id
            assert limit == 100
            self.include_highly_sensitive = include_highly_sensitive
            values = [regular, restricted]
            return values if include_highly_sensitive else [
                item for item in values
                if item.sensitivity_class is not EvidenceSensitivity.HIGHLY_SENSITIVE
            ]

    repository = FakeRepository()

    async def allow_assigned_household(*, session, context, household_id):
        return None

    monkeypatch.setattr(routes, "SqlAlchemyEvidenceRepository", lambda session: repository)
    monkeypatch.setattr(routes, "require_household_assignment", allow_assigned_household)

    response = await routes.list_household_evidence(
        household_id=household_id,
        context=SimpleNamespace(actor_id=uuid4(), scopes=frozenset()),
        session=_Session(),
        limit=100,
    )

    assert repository.include_highly_sensitive is False
    assert [item.id for item in response.data] == [regular.id]


async def test_household_evidence_list_includes_highly_sensitive_with_scope(monkeypatch):
    household_id = uuid4()
    regular = _evidence(household_id, EvidenceSensitivity.INTERNAL)
    restricted = _evidence(household_id, EvidenceSensitivity.HIGHLY_SENSITIVE)

    class FakeRepository:
        async def list_for_household(
            self,
            requested_household_id,
            *,
            limit,
            include_highly_sensitive,
        ):
            assert requested_household_id == household_id
            return [regular, restricted] if include_highly_sensitive else [regular]

    async def allow_assigned_household(*, session, context, household_id):
        return None

    monkeypatch.setattr(routes, "SqlAlchemyEvidenceRepository", lambda session: FakeRepository())
    monkeypatch.setattr(routes, "require_household_assignment", allow_assigned_household)

    response = await routes.list_household_evidence(
        household_id=household_id,
        context=SimpleNamespace(
            actor_id=uuid4(),
            scopes=frozenset({"evidence.highly_sensitive"}),
        ),
        session=_Session(),
        limit=50,
    )

    assert {item.id for item in response.data} == {regular.id, restricted.id}


async def test_repository_filters_sensitive_records_before_applying_limit():
    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: []),
            ),
        ),
    )
    await SqlAlchemyEvidenceRepository(session).list_for_household(
        uuid4(),
        limit=17,
        include_highly_sensitive=False,
    )

    statement = session.execute.await_args.args[0]
    assert "evidence.sensitivity_class !=" in str(statement)
    assert statement._limit_clause.value == 17


def test_evidence_workspace_uses_secure_lifecycle_and_only_downloads_clean_records():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    api = (root / "frontend/src/api/evidence.ts").read_text(encoding="utf-8")
    page = (root / "frontend/src/pages/HouseholdEvidencePage.tsx").read_text(
        encoding="utf-8"
    )
    backend = (root / "src/hamoon/domains/evidence/api/routes.py").read_text(
        encoding="utf-8"
    )

    assert '"/api/v1/households/{household_id}/evidence"' in backend
    assert "/evidence?limit=" in api
    assert "expected_sha256" in api
    assert "evidence.highly_sensitive" in backend
    assert 'item.lifecycle_status === "AVAILABLE" && item.scan_status === "CLEAN"' in page
    assert "getEvidenceDownloadTarget(item.id)" in page
    assert "MAX_UPLOAD_BYTES = 10 * 1024 * 1024" in page
    assert "crypto.subtle.digest" in page
