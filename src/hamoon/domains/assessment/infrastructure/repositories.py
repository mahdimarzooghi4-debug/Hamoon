from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.assessment.domain.entities import (
    AcceptedIndicatorObservation,
    Assessment,
    IndicatorObservation,
    ObservationValidationState,
    ObservationValidationStatus,
)
from hamoon.domains.assessment.infrastructure.models import (
    AcceptedIndicatorObservationModel,
    AcceptedObservationChangeModel,
    AssessmentModel,
    IndicatorObservationModel,
    ObservationValidationChangeModel,
    ObservationValidationStateModel,
)


def _assessment(model: AssessmentModel) -> Assessment:
    return Assessment(
        id=model.id,
        household_id=model.household_id,
        assessment_type=model.assessment_type,
        definition_version_id=model.definition_version_id,
        status=model.status,
        version=model.version,
        started_at=model.started_at,
        started_by=model.started_by,
        reason=model.reason,
        intervention_id=model.intervention_id,
        provider_result_id=model.provider_result_id,
        parent_assessment_id=model.parent_assessment_id,
    )


def _observation(model: IndicatorObservationModel) -> IndicatorObservation:
    return IndicatorObservation(
        id=model.id,
        assessment_id=model.assessment_id,
        indicator_definition_id=model.indicator_definition_id,
        raw_score_0_100=model.raw_score_0_100,
        source_id=model.source_id,
        source_detail=model.source_detail,
        effective_at=model.effective_at,
        observed_at=model.observed_at,
        observed_by=model.observed_by,
        version=model.version,
    )


def _validation(model: ObservationValidationStateModel) -> ObservationValidationState:
    return ObservationValidationState(
        observation_id=model.observation_id,
        status=model.status,
        version=model.version,
        changed_at=model.changed_at,
        changed_by=model.changed_by,
        reason_code=model.reason_code,
        reason_text=model.reason_text,
    )


def _accepted(model: AcceptedIndicatorObservationModel) -> AcceptedIndicatorObservation:
    return AcceptedIndicatorObservation(
        assessment_id=model.assessment_id,
        indicator_definition_id=model.indicator_definition_id,
        observation_id=model.observation_id,
        projection_version=model.projection_version,
        changed_at=model.changed_at,
        changed_by=model.changed_by,
    )


class SqlAlchemyAssessmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, assessment: Assessment) -> None:
        self._session.add(
            AssessmentModel(
                id=assessment.id,
                household_id=assessment.household_id,
                assessment_type=assessment.assessment_type,
                definition_version_id=assessment.definition_version_id,
                status=assessment.status,
                version=assessment.version,
                started_at=assessment.started_at,
                started_by=assessment.started_by,
                reason=assessment.reason,
                intervention_id=assessment.intervention_id,
                provider_result_id=assessment.provider_result_id,
                parent_assessment_id=assessment.parent_assessment_id,
            )
        )

    async def get(self, assessment_id: UUID) -> Assessment | None:
        model = await self._session.get(AssessmentModel, assessment_id)
        return None if model is None else _assessment(model)


class SqlAlchemyIndicatorObservationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, observation: IndicatorObservation) -> None:
        self._session.add(
            IndicatorObservationModel(
                id=observation.id,
                assessment_id=observation.assessment_id,
                indicator_definition_id=observation.indicator_definition_id,
                raw_score_0_100=observation.raw_score_0_100,
                source_id=observation.source_id,
                source_detail=observation.source_detail,
                effective_at=observation.effective_at,
                observed_at=observation.observed_at,
                observed_by=observation.observed_by,
                version=observation.version,
            )
        )

    async def get_for_assessment(
        self,
        *,
        assessment_id: UUID,
        observation_id: UUID,
    ) -> IndicatorObservation | None:
        result = await self._session.execute(
            select(IndicatorObservationModel).where(
                IndicatorObservationModel.assessment_id == assessment_id,
                IndicatorObservationModel.id == observation_id,
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else _observation(model)

    async def list_for_assessment(
        self,
        assessment_id: UUID,
    ) -> list[IndicatorObservation]:
        result = await self._session.execute(
            select(IndicatorObservationModel)
            .where(IndicatorObservationModel.assessment_id == assessment_id)
            .order_by(IndicatorObservationModel.observed_at)
        )
        return [_observation(model) for model in result.scalars().all()]


class SqlAlchemyObservationValidationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_initial(
        self,
        state: ObservationValidationState,
    ) -> None:
        self._session.add(
            ObservationValidationStateModel(
                observation_id=state.observation_id,
                status=state.status,
                version=state.version,
                changed_at=state.changed_at,
                changed_by=state.changed_by,
                reason_code=state.reason_code,
                reason_text=state.reason_text,
            )
        )
        self._session.add(
            ObservationValidationChangeModel(
                id=uuid4(),
                observation_id=state.observation_id,
                validation_version=state.version,
                from_status=None,
                to_status=state.status,
                reason_code=state.reason_code,
                reason_text=state.reason_text,
                changed_at=state.changed_at,
                changed_by=state.changed_by,
            )
        )

    async def get_state(
        self,
        observation_id: UUID,
    ) -> ObservationValidationState | None:
        model = await self._session.get(ObservationValidationStateModel, observation_id)
        return None if model is None else _validation(model)

    async def transition(
        self,
        *,
        previous: ObservationValidationState,
        current: ObservationValidationState,
    ) -> None:
        model = await self._session.get(
            ObservationValidationStateModel,
            previous.observation_id,
        )
        if model is None:
            raise RuntimeError("Observation validation state is missing.")
        if model.version != previous.version:
            raise RuntimeError("Observation validation version changed.")

        model.status = current.status
        model.version = current.version
        model.changed_at = current.changed_at
        model.changed_by = current.changed_by
        model.reason_code = current.reason_code
        model.reason_text = current.reason_text

        self._session.add(
            ObservationValidationChangeModel(
                id=uuid4(),
                observation_id=current.observation_id,
                validation_version=current.version,
                from_status=previous.status,
                to_status=current.status,
                reason_code=current.reason_code,
                reason_text=current.reason_text,
                changed_at=current.changed_at,
                changed_by=current.changed_by,
            )
        )

    async def count_unresolved_for_assessment(
        self,
        assessment_id: UUID,
    ) -> int:
        result = await self._session.execute(
            select(func.count(ObservationValidationStateModel.observation_id))
            .join(
                IndicatorObservationModel,
                IndicatorObservationModel.id
                == ObservationValidationStateModel.observation_id,
            )
            .where(
                IndicatorObservationModel.assessment_id == assessment_id,
                or_(
                    ObservationValidationStateModel.status
                    == ObservationValidationStatus.PENDING_VALIDATION,
                    ObservationValidationStateModel.status
                    == ObservationValidationStatus.DISPUTED,
                ),
            )
        )
        return int(result.scalar_one())


class SqlAlchemyAcceptedObservationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        *,
        assessment_id: UUID,
        indicator_definition_id: UUID,
    ) -> AcceptedIndicatorObservation | None:
        result = await self._session.execute(
            select(AcceptedIndicatorObservationModel).where(
                AcceptedIndicatorObservationModel.assessment_id == assessment_id,
                AcceptedIndicatorObservationModel.indicator_definition_id
                == indicator_definition_id,
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else _accepted(model)

    async def list_for_assessment(
        self,
        assessment_id: UUID,
    ) -> list[AcceptedIndicatorObservation]:
        result = await self._session.execute(
            select(AcceptedIndicatorObservationModel)
            .where(AcceptedIndicatorObservationModel.assessment_id == assessment_id)
            .order_by(AcceptedIndicatorObservationModel.indicator_definition_id)
        )
        return [_accepted(model) for model in result.scalars().all()]

    async def set_current(
        self,
        *,
        accepted: AcceptedIndicatorObservation,
        previous_observation_id: UUID | None,
        reason_code: str,
        reason_text: str | None,
        event_id: UUID,
    ) -> None:
        result = await self._session.execute(
            select(AcceptedIndicatorObservationModel).where(
                AcceptedIndicatorObservationModel.assessment_id
                == accepted.assessment_id,
                AcceptedIndicatorObservationModel.indicator_definition_id
                == accepted.indicator_definition_id,
            )
        )
        model = result.scalar_one_or_none()

        if model is None:
            model = AcceptedIndicatorObservationModel(
                id=uuid4(),
                assessment_id=accepted.assessment_id,
                indicator_definition_id=accepted.indicator_definition_id,
                observation_id=accepted.observation_id,
                projection_version=accepted.projection_version,
                changed_at=accepted.changed_at,
                changed_by=accepted.changed_by,
            )
            self._session.add(model)
        else:
            model.observation_id = accepted.observation_id
            model.projection_version = accepted.projection_version
            model.changed_at = accepted.changed_at
            model.changed_by = accepted.changed_by

        self._session.add(
            AcceptedObservationChangeModel(
                id=uuid4(),
                assessment_id=accepted.assessment_id,
                indicator_definition_id=accepted.indicator_definition_id,
                previous_observation_id=previous_observation_id,
                new_observation_id=accepted.observation_id,
                projection_version=accepted.projection_version,
                reason_code=reason_code,
                reason_text=reason_text,
                changed_at=accepted.changed_at,
                changed_by=accepted.changed_by,
                domain_event_id=event_id,
            )
        )
