from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.security.context import AuthorizationContext
from hamoon.domains.household.infrastructure.repositories import (
    SqlAlchemyCaseAssignmentRepository,
)


async def require_household_assignment(
    *,
    session: AsyncSession,
    context: AuthorizationContext,
    household_id: UUID,
) -> None:
    assignments = SqlAlchemyCaseAssignmentRepository(session)
    allowed = await assignments.has_active_assignment(
        household_id=household_id,
        actor_id=context.actor_id,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND"},
        )
