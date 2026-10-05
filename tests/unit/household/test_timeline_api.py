from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.household.api import routes as household_routes
from hamoon.domains.household.domain.entities import Household, HouseholdStatus
from hamoon.domains.household.infrastructure.timeline import (
    HouseholdTimelineItem,
    SqlAlchemyHouseholdTimelineRepository,
)
from hamoon.domains.identity.domain.entities import ActorType

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD_ID = UUID("22222222-2222-2222-2222-222222222222")


class _Scalars:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def all(self) -> list[object]:
        return self._items


class _Result:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def scalars(self) -> _Scalars:
        return _Scalars(self._items)


class _Session:
    def __init__(self, responses: list[list[object]]) -> None:
        self._responses = iter(responses)

    async def execute(self, _statement: object) -> _Result:
        return _Result(next(self._responses))


@pytest.mark.asyncio
async def test_timeline_repository_orders_cross_domain_items_without_provider_text() -> None:
    def day(value: int) -> datetime:
        return datetime(2026, 10, value, tzinfo=UTC)

    responses = [
        [
            SimpleNamespace(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                recorded_at=day(1),
                fact_type="income_band",
            )
        ],
        [
            SimpleNamespace(
                id=UUID("00000000-0000-0000-0000-000000000002"),
                started_at=day(2),
                status="COMPLETED",
                assessment_type="BASELINE",
            )
        ],
        [
            SimpleNamespace(
                id=UUID("00000000-0000-0000-0000-000000000003"),
                calculated_at=day(3),
                status="OFFICIAL",
                e_band="SUPPORTED_EMPOWERMENT",
            )
        ],
        [
            SimpleNamespace(
                id=UUID("00000000-0000-0000-0000-000000000004"),
                created_at=day(4),
                status="CONFIRMED",
            )
        ],
        [
            SimpleNamespace(
                id=UUID("00000000-0000-0000-0000-000000000005"),
                created_at=day(5),
                status="ACCEPTED",
            )
        ],
        [
            SimpleNamespace(
                id=UUID("00000000-0000-0000-0000-000000000006"),
                created_at=day(6),
                status="SENT",
            )
        ],
        [
            SimpleNamespace(
                id=UUID("00000000-0000-0000-0000-000000000007"),
                submitted_at=day(7),
                result_status="COMPLETED",
                result_type="SERVICE_RESULT",
                result_summary="provider free text must not enter timeline",
            )
        ],
        [
            SimpleNamespace(
                id=UUID("00000000-0000-0000-0000-000000000008"),
                assessed_at=day(8),
                status="REVIEW_REQUIRED",
                classification=None,
            )
        ],
    ]

    repository = SqlAlchemyHouseholdTimelineRepository(
        cast(AsyncSession, _Session(responses))
    )
    items = await repository.list_for_household(
        household_id=HOUSEHOLD_ID,
        limit=200,
    )

    assert [item.kind for item in items] == [
        "OUTCOME",
        "PROVIDER_RESULT",
        "REFERRAL",
        "PRESCRIPTION",
        "DIAGNOSIS",
        "PGOR",
        "ASSESSMENT",
        "FACT",
    ]
    provider_result = next(
        item for item in items if item.kind == "PROVIDER_RESULT"
    )
    assert provider_result.detail == "SERVICE_RESULT"
    assert "provider free text" not in repr(items)


class _Households:
    async def get(self, household_id: UUID) -> Household | None:
        if household_id != HOUSEHOLD_ID:
            return None
        return Household(
            id=HOUSEHOLD_ID,
            case_code="H-1405-21842",
            lifecycle_status=HouseholdStatus.ACTIVE,
            organizational_unit_id="unit-12",
            primary_caseworker_id=ACTOR_ID,
            version=3,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_by=ACTOR_ID,
        )


class _Timeline:
    async def list_for_household(
        self,
        *,
        household_id: UUID,
        limit: int,
    ) -> list[HouseholdTimelineItem]:
        assert household_id == HOUSEHOLD_ID
        assert limit == 25
        return [
            HouseholdTimelineItem(
                kind="PGOR",
                entity_id=UUID("00000000-0000-0000-0000-000000000009"),
                occurred_at=datetime(2026, 10, 3, tzinfo=UTC),
                status="OFFICIAL",
                detail="E_BAND:SUPPORTED_EMPOWERMENT",
            )
        ]


def _context() -> AuthorizationContext:
    return AuthorizationContext(
        actor_id=ACTOR_ID,
        actor_type=ActorType.HUMAN,
        subject="caseworker",
        issuer="https://identity.local",
        roles=frozenset({Role.CASEWORKER}),
        scopes=frozenset(),
    )


@pytest.mark.asyncio
async def test_timeline_endpoint_requires_household_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scoped: list[UUID] = []

    async def require_scope(
        *,
        session: AsyncSession,
        context: AuthorizationContext,
        household_id: UUID,
    ) -> None:
        del session, context
        scoped.append(household_id)

    monkeypatch.setattr(
        household_routes,
        "SqlAlchemyHouseholdRepository",
        lambda _session: _Households(),
    )
    monkeypatch.setattr(
        household_routes,
        "SqlAlchemyHouseholdTimelineRepository",
        lambda _session: _Timeline(),
    )
    monkeypatch.setattr(
        household_routes,
        "require_household_assignment",
        require_scope,
    )

    response = await household_routes.get_household_timeline(
        HOUSEHOLD_ID,
        _context(),
        cast(AsyncSession, object()),
        limit=25,
    )

    assert scoped == [HOUSEHOLD_ID]
    assert len(response.data) == 1
    assert response.data[0].kind == "PGOR"
    assert response.data[0].status == "OFFICIAL"
