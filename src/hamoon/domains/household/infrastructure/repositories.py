from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.household.domain.entities import CaseAssignment, Household, HouseholdStatus
from hamoon.domains.household.infrastructure.models import (
    CaseAssignmentModel,
    HouseholdModel,
)


def _to_household(model: HouseholdModel) -> Household:
    return Household(
        id=model.id,
        case_code=model.case_code,
        lifecycle_status=model.lifecycle_status,
        organizational_unit_id=model.organizational_unit_id,
        primary_caseworker_id=model.primary_caseworker_id,
        version=model.version,
        created_at=model.created_at,
        created_by=model.created_by,
        closed_at=model.closed_at,
    )


class SqlAlchemyHouseholdRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, household: Household) -> None:
        self._session.add(
            HouseholdModel(
                id=household.id,
                case_code=household.case_code,
                lifecycle_status=household.lifecycle_status,
                organizational_unit_id=household.organizational_unit_id,
                primary_caseworker_id=household.primary_caseworker_id,
                version=household.version,
                created_at=household.created_at,
                created_by=household.created_by,
                closed_at=household.closed_at,
            )
        )

    async def get(self, household_id: UUID) -> Household | None:
        model = await self._session.get(HouseholdModel, household_id)
        return None if model is None else _to_household(model)

    async def get_by_case_code(self, case_code: str) -> Household | None:
        result = await self._session.execute(
            select(HouseholdModel).where(HouseholdModel.case_code == case_code)
        )
        model = result.scalar_one_or_none()
        return None if model is None else _to_household(model)


    async def list_for_actor(
        self,
        *,
        actor_id: UUID,
        query: str | None,
        lifecycle_status: HouseholdStatus | None,
        limit: int,
    ) -> list[Household]:
        now = datetime.now(UTC)
        statement = (
            select(HouseholdModel)
            .join(
                CaseAssignmentModel,
                CaseAssignmentModel.household_id == HouseholdModel.id,
            )
            .where(
                CaseAssignmentModel.actor_id == actor_id,
                CaseAssignmentModel.valid_from <= now,
                or_(
                    CaseAssignmentModel.valid_to.is_(None),
                    CaseAssignmentModel.valid_to > now,
                ),
            )
        )
        if query:
            statement = statement.where(
                HouseholdModel.case_code.ilike(f"%{query}%")
            )
        if lifecycle_status is not None:
            statement = statement.where(
                HouseholdModel.lifecycle_status == lifecycle_status
            )
        statement = (
            statement.distinct()
            .order_by(HouseholdModel.case_code)
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return [_to_household(model) for model in result.scalars().all()]


class SqlAlchemyCaseAssignmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, assignment: CaseAssignment) -> None:
        self._session.add(
            CaseAssignmentModel(
                id=assignment.id,
                household_id=assignment.household_id,
                actor_id=assignment.actor_id,
                assignment_type=assignment.assignment_type,
                valid_from=assignment.valid_from,
                valid_to=assignment.valid_to,
                assigned_by=assignment.assigned_by,
                reason=assignment.reason,
                created_at=assignment.created_at,
            )
        )

    async def has_active_assignment(
        self,
        *,
        household_id: UUID,
        actor_id: UUID,
    ) -> bool:
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(CaseAssignmentModel.id)
            .where(
                CaseAssignmentModel.household_id == household_id,
                CaseAssignmentModel.actor_id == actor_id,
                CaseAssignmentModel.valid_from <= now,
                or_(
                    CaseAssignmentModel.valid_to.is_(None),
                    CaseAssignmentModel.valid_to > now,
                ),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
