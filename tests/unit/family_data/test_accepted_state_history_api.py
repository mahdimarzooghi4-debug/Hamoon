"""Accepted State human decision history: scoped, bounded and cursor-paginated."""

from dataclasses import asdict
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.family_data.api import routes
from hamoon.domains.family_data.domain.entities import AcceptedStateChange
from hamoon.domains.family_data.infrastructure.repositories import (
    SqlAlchemyAcceptedStateRepository,
)
from hamoon.domains.identity.domain.entities import ActorType

HOUSEHOLD = UUID("22222222-2222-2222-2222-222222222222")
OTHER_HOUSEHOLD = UUID("33333333-3333-3333-3333-333333333333")
ACTOR = UUID("11111111-1111-1111-1111-111111111111")
FACT1 = UUID("44444444-4444-4444-4444-444444444444")
FACT2 = UUID("55555555-5555-5555-5555-555555555555")


def _context() -> AuthorizationContext:
    return AuthorizationContext(
        actor_id=ACTOR,
        actor_type=ActorType.HUMAN,
        subject="caseworker",
        issuer="https://identity.local",
        roles=frozenset({Role.CASEWORKER}),
        scopes=frozenset(),
    )


def _change(version: int) -> AcceptedStateChange:
    return AcceptedStateChange(
        id=UUID(f"00000000-0000-0000-0000-{version:012d}"),
        household_id=HOUSEHOLD,
        fact_type="EMPLOYMENT_STATUS",
        previous_fact_id=None if version == 1 else FACT1,
        new_fact_id=FACT1 if version == 1 else FACT2,
        projection_version=version,
        reason_code="HUMAN_RESOLUTION",
        reason_text="reviewed source",
        changed_by=ACTOR,
        changed_at=datetime(2026, 10, 25, tzinfo=UTC),
        domain_event_id=UUID(f"10000000-0000-0000-0000-{version:012d}"),
    )


class _Scalars:
    def __init__(self, items: list[object]) -> None:
        self.items = items

    def all(self) -> list[object]:
        return self.items


class _Result:
    def __init__(self, items: list[object]) -> None:
        self.items = items

    def scalars(self) -> _Scalars:
        return _Scalars(self.items)


class _Session:
    def __init__(self, items: list[object]) -> None:
        self.items = items
        self.statement: object | None = None

    async def execute(self, statement: object) -> _Result:
        self.statement = statement
        return _Result(self.items)


@pytest.mark.asyncio
async def test_history_sql_scopes_before_pagination_and_uses_version_cursor() -> None:
    items = [
        SimpleNamespace(**asdict(_change(version)))
        for version in (9, 8, 7)
    ]
    session = _Session(items)
    changes, has_more = await SqlAlchemyAcceptedStateRepository(
        cast(AsyncSession, session)
    ).list_history(
        household_id=HOUSEHOLD,
        fact_type="EMPLOYMENT_STATUS",
        limit=2,
        before_version=10,
    )
    assert [item.projection_version for item in changes] == [9, 8]
    assert has_more is True
    assert session.statement is not None
    sql = str(
        session.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert str(HOUSEHOLD) in sql
    assert "EMPLOYMENT_STATUS" in sql
    assert "projection_version < 10" in sql
    assert "LIMIT 3" in sql
    assert "projection_version DESC" in sql


@pytest.mark.asyncio
async def test_history_endpoint_checks_assignment_and_returns_a_real_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scopes: list[UUID] = []

    async def require_scope(
        *, session: AsyncSession, context: AuthorizationContext, household_id: UUID
    ) -> None:
        del session, context
        scopes.append(household_id)

    class _History:
        async def list_history(
            self,
            *,
            household_id: UUID,
            fact_type: str,
            limit: int,
            before_version: int | None,
        ) -> tuple[list[AcceptedStateChange], bool]:
            assert household_id == HOUSEHOLD
            assert fact_type == "EMPLOYMENT_STATUS"
            assert limit == 2
            assert before_version == 10
            return [_change(9), _change(8)], True

    monkeypatch.setattr(routes, "require_household_assignment", require_scope)
    monkeypatch.setattr(
        routes, "SqlAlchemyAcceptedStateRepository", lambda _session: _History()
    )
    result = await routes.get_accepted_state_history(
        HOUSEHOLD,
        "employment_status",
        _context(),
        cast(AsyncSession, object()),
        limit=2,
        before_version=10,
    )
    assert scopes == [HOUSEHOLD]
    assert result.next_before_version == 8
    assert [row.projection_version for row in result.data] == [9, 8]
    assert result.data[0].reason_text == "reviewed source"
    assert result.data[0].changed_by == ACTOR


@pytest.mark.asyncio
async def test_unassigned_household_never_reads_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def deny(
        *, session: AsyncSession, context: AuthorizationContext, household_id: UUID
    ) -> None:
        del session, context, household_id
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND"})

    def forbidden_repository(_session: AsyncSession) -> object:
        raise AssertionError("Repository must not run without assignment")

    monkeypatch.setattr(routes, "require_household_assignment", deny)
    monkeypatch.setattr(
        routes, "SqlAlchemyAcceptedStateRepository", forbidden_repository
    )
    with pytest.raises(HTTPException) as exc:
        await routes.get_accepted_state_history(
            OTHER_HOUSEHOLD,
            "EMPLOYMENT_STATUS",
            _context(),
            cast(AsyncSession, object()),
            limit=50,
            before_version=None,
        )
    assert exc.value.status_code == 404


def test_history_route_is_role_gated_and_query_bounded() -> None:
    from fastapi.routing import APIRoute

    route = next(
        item for item in routes.router.routes
        if getattr(item, "path", "") ==
        "/api/v1/households/{household_id}/accepted-state/{fact_type}/history"
    )
    assert isinstance(route, APIRoute)
    schema = route.dependant
    limit = next(
        parameter for parameter in schema.query_params if parameter.name == "limit"
    )
    before = next(
        parameter for parameter in schema.query_params
        if parameter.name == "before_version"
    )
    assert any(getattr(item, "ge", None) == 1 for item in limit.field_info.metadata)
    assert any(getattr(item, "le", None) == 100 for item in limit.field_info.metadata)
    assert any(getattr(item, "ge", None) == 1 for item in before.field_info.metadata)
    assert route.methods == {"GET"}
