from uuid import UUID

import pytest
from fastapi import HTTPException

from hamoon.app.security import resource_scope
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.identity.domain.entities import ActorType

ACTOR = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD = UUID("22222222-2222-2222-2222-222222222222")


@pytest.mark.asyncio
async def test_unassigned_household_is_hidden_as_not_found(monkeypatch) -> None:
    class Assignments:
        def __init__(self, _session) -> None:
            pass

        async def has_active_assignment(self, *, household_id, actor_id):
            assert household_id == HOUSEHOLD
            assert actor_id == ACTOR
            return False

    monkeypatch.setattr(
        resource_scope,
        "SqlAlchemyCaseAssignmentRepository",
        Assignments,
    )
    context = AuthorizationContext(
        actor_id=ACTOR,
        actor_type=ActorType.HUMAN,
        subject="subject",
        issuer="issuer",
        roles=frozenset({Role.CASEWORKER}),
        scopes=frozenset(),
    )

    with pytest.raises(HTTPException) as exc:
        await resource_scope.require_household_assignment(
            session=object(),
            context=context,
            household_id=HOUSEHOLD,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == {"code": "RESOURCE_NOT_FOUND"}
