from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.intervention.domain.entities import Intervention
from hamoon.domains.intervention.infrastructure.models import InterventionModel


def _intervention(model: InterventionModel) -> Intervention:
    return Intervention(
        id=model.id,
        household_id=model.household_id,
        prescription_item_id=model.prescription_item_id,
        intervention_type=model.intervention_type,
        target_pgor_variable=model.target_pgor_variable,
        status=model.status,
        started_at=model.started_at,
        completed_at=model.completed_at,
        owner_actor_id=model.owner_actor_id,
    )


class SqlAlchemyInterventionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, intervention: Intervention) -> None:
        self._session.add(
            InterventionModel(
                id=intervention.id,
                household_id=intervention.household_id,
                prescription_item_id=intervention.prescription_item_id,
                intervention_type=intervention.intervention_type,
                target_pgor_variable=intervention.target_pgor_variable,
                status=intervention.status,
                started_at=intervention.started_at,
                completed_at=intervention.completed_at,
                owner_actor_id=intervention.owner_actor_id,
            )
        )

    async def get(self, intervention_id: UUID) -> Intervention | None:
        model = await self._session.get(InterventionModel, intervention_id)
        return None if model is None else _intervention(model)

    async def get_by_prescription_item(
        self,
        prescription_item_id: UUID,
    ) -> Intervention | None:
        result = await self._session.execute(
            select(InterventionModel).where(
                InterventionModel.prescription_item_id == prescription_item_id
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else _intervention(model)

    async def list_for_household(self, household_id: UUID) -> list[Intervention]:
        result = await self._session.execute(
            select(InterventionModel)
            .where(InterventionModel.household_id == household_id)
            .order_by(InterventionModel.started_at.desc())
        )
        return [_intervention(model) for model in result.scalars().all()]
