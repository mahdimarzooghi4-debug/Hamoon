from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.identity.domain.entities import ActorType
from hamoon.domains.learning.api import routes as learning_routes
from hamoon.domains.learning.domain.entities import (
    DatasetVersionStatus,
    LearningDatasetVersion,
)

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
DATASET_ID = UUID("22222222-2222-2222-2222-222222222222")


def _context() -> AuthorizationContext:
    return AuthorizationContext(
        actor_id=ACTOR_ID,
        actor_type=ActorType.HUMAN,
        subject="admin",
        issuer="https://identity.local",
        roles=frozenset({Role.ADMIN}),
        scopes=frozenset(),
    )


class Datasets:
    async def list_versions(
        self,
        *,
        status: DatasetVersionStatus | None = None,
        limit: int = 100,
    ) -> list[LearningDatasetVersion]:
        assert status is DatasetVersionStatus.APPROVED
        assert limit == 25
        return [
            LearningDatasetVersion(
                id=DATASET_ID,
                dataset_key="outcome-review",
                version="2026-10-04",
                purpose="OUTCOME_INTERPRETATION",
                selection_policy_version="outcome-selection-v1",
                status=DatasetVersionStatus.APPROVED,
                manifest_ref="db://learning-dataset/1",
                manifest_digest="a" * 64,
                created_at=datetime(2026, 10, 4, tzinfo=UTC),
                created_by=ACTOR_ID,
                approved_at=datetime(2026, 10, 4, 1, tzinfo=UTC),
                approved_by=ACTOR_ID,
            )
        ]

    async def item_counts(self, dataset_ids: list[UUID]) -> dict[UUID, int]:
        assert dataset_ids == [DATASET_ID]
        return {DATASET_ID: 7}


@pytest.mark.asyncio
async def test_admin_can_list_learning_datasets_with_item_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        learning_routes,
        "SqlAlchemyLearningDatasetRepository",
        lambda _session: Datasets(),
    )

    response = await learning_routes.list_learning_datasets(
        _context(),
        cast(AsyncSession, object()),
        dataset_status=DatasetVersionStatus.APPROVED,
        limit=25,
    )

    assert len(response.data) == 1
    item = response.data[0]
    assert item.id == DATASET_ID
    assert item.status is DatasetVersionStatus.APPROVED
    assert item.item_count == 7
    assert item.manifest_digest == "a" * 64
