from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.family_data.domain.entities import (
    CurrentAcceptedFact,
    DataSource,
    FactValidationState,
    HouseholdFact,
)
from hamoon.domains.family_data.infrastructure.models import (
    AcceptedStateChangeModel,
    CurrentAcceptedFactModel,
    DataSourceModel,
    FactValidationChangeModel,
    FactValidationStateModel,
    HouseholdFactModel,
)


def _to_source(model: DataSourceModel) -> DataSource:
    return DataSource(
        id=model.id,
        code=model.code,
        source_type=model.source_type,
        name=model.name,
        active=model.active,
    )


def _to_fact(model: HouseholdFactModel) -> HouseholdFact:
    return HouseholdFact(
        id=model.id,
        household_id=model.household_id,
        fact_type=model.fact_type,
        value_type=model.value_type,
        value=model.value,
        source_id=model.source_id,
        source_detail=model.source_detail,
        effective_from=model.effective_from,
        effective_to=model.effective_to,
        recorded_at=model.recorded_at,
        recorded_by=model.recorded_by,
        version=model.version,
        supersedes_fact_id=model.supersedes_fact_id,
        schema_version=model.schema_version,
    )


def _to_validation(model: FactValidationStateModel) -> FactValidationState:
    return FactValidationState(
        fact_id=model.fact_id,
        status=model.status,
        version=model.version,
        changed_at=model.changed_at,
        changed_by=model.changed_by,
        reason_code=model.reason_code,
        reason_text=model.reason_text,
    )


def _to_accepted(model: CurrentAcceptedFactModel) -> CurrentAcceptedFact:
    return CurrentAcceptedFact(
        household_id=model.household_id,
        fact_type=model.fact_type,
        fact_id=model.fact_id,
        accepted_value=model.accepted_value,
        source_id=model.source_id,
        effective_from=model.effective_from,
        projection_version=model.projection_version,
        projected_at=model.projected_at,
        changed_by=model.changed_by,
    )


class SqlAlchemyDataSourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, source_id: UUID) -> DataSource | None:
        model = await self._session.get(DataSourceModel, source_id)
        return None if model is None else _to_source(model)

    async def list_active(self) -> list[DataSource]:
        result = await self._session.execute(
            select(DataSourceModel)
            .where(DataSourceModel.active.is_(True))
            .order_by(DataSourceModel.code)
        )
        return [_to_source(model) for model in result.scalars().all()]


class SqlAlchemyHouseholdFactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, fact: HouseholdFact) -> None:
        self._session.add(
            HouseholdFactModel(
                id=fact.id,
                household_id=fact.household_id,
                fact_type=fact.fact_type,
                value_type=fact.value_type,
                value=fact.value,
                source_id=fact.source_id,
                source_detail=fact.source_detail,
                effective_from=fact.effective_from,
                effective_to=fact.effective_to,
                recorded_at=fact.recorded_at,
                recorded_by=fact.recorded_by,
                version=fact.version,
                supersedes_fact_id=fact.supersedes_fact_id,
                schema_version=fact.schema_version,
            )
        )

    async def get_for_household(
        self,
        *,
        household_id: UUID,
        fact_id: UUID,
    ) -> HouseholdFact | None:
        result = await self._session.execute(
            select(HouseholdFactModel).where(
                HouseholdFactModel.household_id == household_id,
                HouseholdFactModel.id == fact_id,
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else _to_fact(model)

    async def list_for_household(self, household_id: UUID) -> list[HouseholdFact]:
        result = await self._session.execute(
            select(HouseholdFactModel)
            .where(HouseholdFactModel.household_id == household_id)
            .order_by(HouseholdFactModel.recorded_at.desc())
        )
        return [_to_fact(model) for model in result.scalars().all()]


class SqlAlchemyFactValidationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_initial(
        self,
        *,
        state: FactValidationState,
        occurred_at: datetime,
    ) -> None:
        self._session.add(
            FactValidationStateModel(
                fact_id=state.fact_id,
                status=state.status,
                version=state.version,
                changed_at=state.changed_at,
                changed_by=state.changed_by,
                reason_code=state.reason_code,
                reason_text=state.reason_text,
            )
        )
        self._session.add(
            FactValidationChangeModel(
                id=uuid4(),
                fact_id=state.fact_id,
                validation_version=state.version,
                from_status=None,
                to_status=state.status,
                reason_code=state.reason_code,
                reason_text=state.reason_text,
                changed_at=occurred_at,
                changed_by=state.changed_by,
            )
        )

    async def get_state(self, fact_id: UUID) -> FactValidationState | None:
        model = await self._session.get(FactValidationStateModel, fact_id)
        return None if model is None else _to_validation(model)

    async def transition(
        self,
        *,
        previous: FactValidationState,
        current: FactValidationState,
    ) -> None:
        model = await self._session.get(FactValidationStateModel, previous.fact_id)
        if model is None:
            raise RuntimeError("Validation projection is missing.")

        if model.version != previous.version:
            raise RuntimeError("Validation projection version changed.")

        model.status = current.status
        model.version = current.version
        model.changed_at = current.changed_at
        model.changed_by = current.changed_by
        model.reason_code = current.reason_code
        model.reason_text = current.reason_text

        self._session.add(
            FactValidationChangeModel(
                id=uuid4(),
                fact_id=current.fact_id,
                validation_version=current.version,
                from_status=previous.status,
                to_status=current.status,
                reason_code=current.reason_code,
                reason_text=current.reason_text,
                changed_at=current.changed_at,
                changed_by=current.changed_by,
            )
        )


class SqlAlchemyAcceptedStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        *,
        household_id: UUID,
        fact_type: str,
    ) -> CurrentAcceptedFact | None:
        result = await self._session.execute(
            select(CurrentAcceptedFactModel).where(
                CurrentAcceptedFactModel.household_id == household_id,
                CurrentAcceptedFactModel.fact_type == fact_type,
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else _to_accepted(model)

    async def list_for_household(
        self,
        household_id: UUID,
    ) -> list[CurrentAcceptedFact]:
        result = await self._session.execute(
            select(CurrentAcceptedFactModel)
            .where(CurrentAcceptedFactModel.household_id == household_id)
            .order_by(CurrentAcceptedFactModel.fact_type)
        )
        return [_to_accepted(model) for model in result.scalars().all()]

    async def set_current(
        self,
        *,
        accepted: CurrentAcceptedFact,
        previous_fact_id: UUID | None,
        reason_code: str,
        reason_text: str | None,
        event_id: UUID,
    ) -> None:
        result = await self._session.execute(
            select(CurrentAcceptedFactModel).where(
                CurrentAcceptedFactModel.household_id == accepted.household_id,
                CurrentAcceptedFactModel.fact_type == accepted.fact_type,
            )
        )
        model = result.scalar_one_or_none()

        if model is None:
            model = CurrentAcceptedFactModel(
                id=uuid4(),
                household_id=accepted.household_id,
                fact_type=accepted.fact_type,
                fact_id=accepted.fact_id,
                accepted_value=accepted.accepted_value,
                source_id=accepted.source_id,
                effective_from=accepted.effective_from,
                projection_version=accepted.projection_version,
                projected_at=accepted.projected_at,
                changed_by=accepted.changed_by,
            )
            self._session.add(model)
        else:
            model.fact_id = accepted.fact_id
            model.accepted_value = accepted.accepted_value
            model.source_id = accepted.source_id
            model.effective_from = accepted.effective_from
            model.projection_version = accepted.projection_version
            model.projected_at = accepted.projected_at
            model.changed_by = accepted.changed_by

        self._session.add(
            AcceptedStateChangeModel(
                id=uuid4(),
                household_id=accepted.household_id,
                fact_type=accepted.fact_type,
                previous_fact_id=previous_fact_id,
                new_fact_id=accepted.fact_id,
                projection_version=accepted.projection_version,
                reason_code=reason_code,
                reason_text=reason_text,
                changed_by=accepted.changed_by,
                changed_at=accepted.projected_at,
                domain_event_id=event_id,
            )
        )
