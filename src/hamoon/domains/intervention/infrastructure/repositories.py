from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.intervention.domain.entities import Intervention, InterventionStatus
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


    async def list_current_for_households(
        self,
        household_ids: list[UUID],
    ) -> dict[UUID, Intervention]:
        if not household_ids:
            return {}
        status_priority = case(
            (InterventionModel.status == InterventionStatus.ACTIVE, 0),
            (InterventionModel.status == InterventionStatus.REFERRED, 1),
            (InterventionModel.status == InterventionStatus.READY_FOR_REFERRAL, 2),
            (InterventionModel.status == InterventionStatus.PLANNED, 3),
            else_=4,
        )
        ranked = (
            select(
                InterventionModel.id.label("intervention_id"),
                func.row_number()
                .over(
                    partition_by=InterventionModel.household_id,
                    order_by=(
                        status_priority,
                        InterventionModel.started_at.desc().nulls_last(),
                        InterventionModel.id,
                    ),
                )
                .label("row_number"),
            )
            .where(
                InterventionModel.household_id.in_(household_ids),
                InterventionModel.status.in_(
                    (
                        InterventionStatus.PLANNED,
                        InterventionStatus.READY_FOR_REFERRAL,
                        InterventionStatus.REFERRED,
                        InterventionStatus.ACTIVE,
                    )
                ),
            )
            .subquery()
        )
        result = await self._session.execute(
            select(InterventionModel)
            .join(ranked, InterventionModel.id == ranked.c.intervention_id)
            .where(ranked.c.row_number == 1)
        )
        return {
            model.household_id: _intervention(model)
            for model in result.scalars().all()
        }
