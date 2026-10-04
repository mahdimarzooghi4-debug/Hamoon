from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.identity.domain.entities import ActorType
from hamoon.domains.operations.api import routes as operations_routes
from hamoon.domains.operations.domain.entities import (
    ReassessmentPlan,
    ReassessmentPlanStatus,
)

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD_ID = UUID("22222222-2222-2222-2222-222222222222")
PLAN_ID = UUID("33333333-3333-3333-3333-333333333333")
INTERVENTION_ID = UUID("44444444-4444-4444-4444-444444444444")
RESULT_ID = UUID("55555555-5555-5555-5555-555555555555")
PRESCRIPTION_ITEM_ID = UUID("66666666-6666-6666-6666-666666666666")
WORK_ITEM_ID = UUID("77777777-7777-7777-7777-777777777777")


def _plan() -> ReassessmentPlan:
    now = datetime(2026, 10, 4, tzinfo=UTC)
    return ReassessmentPlan(
        id=PLAN_ID,
        household_id=HOUSEHOLD_ID,
        intervention_id=INTERVENTION_ID,
        provider_result_id=RESULT_ID,
        prescription_item_id=PRESCRIPTION_ITEM_ID,
        assigned_actor_id=ACTOR_ID,
        review_after_days=30,
        due_at=now + timedelta(days=30),
        policy_version="prescription-item-review-v1",
        workflow_id=f"reassessment:{PLAN_ID}",
        status=ReassessmentPlanStatus.TASK_CREATED,
        version=2,
        created_at=now,
        created_by=ACTOR_ID,
        work_item_id=WORK_ITEM_ID,
        task_created_at=now + timedelta(minutes=1),
    )


class Plans:
    def __init__(self, item: ReassessmentPlan | None) -> None:
        self.item = item

    async def get(self, plan_id: UUID) -> ReassessmentPlan | None:
        if self.item is not None and plan_id == PLAN_ID:
            return self.item
        return None


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
async def test_caseworker_can_read_reassessment_plan(
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
        operations_routes,
        "SqlAlchemyReassessmentPlanRepository",
        lambda _session: Plans(_plan()),
    )
    monkeypatch.setattr(
        operations_routes,
        "require_household_assignment",
        require_scope,
    )

    response = await operations_routes.get_reassessment_plan(
        PLAN_ID,
        _context(),
        cast(AsyncSession, object()),
    )

    assert scoped == [HOUSEHOLD_ID]
    assert response.data.id == PLAN_ID
    assert response.data.status is ReassessmentPlanStatus.TASK_CREATED
    assert response.data.work_item_id == WORK_ITEM_ID
    assert response.data.due_at == datetime(2026, 11, 3, tzinfo=UTC)
    assert response.data.post_assessment_id is None
    assert response.data.outcome_id is None


@pytest.mark.asyncio
async def test_reassessment_plan_read_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        operations_routes,
        "SqlAlchemyReassessmentPlanRepository",
        lambda _session: Plans(None),
    )

    with pytest.raises(HTTPException) as exc_info:
        await operations_routes.get_reassessment_plan(
            PLAN_ID,
            _context(),
            cast(AsyncSession, object()),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == {"code": "RESOURCE_NOT_FOUND"}
