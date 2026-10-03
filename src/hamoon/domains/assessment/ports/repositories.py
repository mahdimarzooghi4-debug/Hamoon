from datetime import datetime
from typing import Protocol
from uuid import UUID

from hamoon.domains.assessment.domain.entities import (
    AcceptedIndicatorObservation,
    Assessment,
    IndicatorObservation,
    ObservationValidationState,
    ObservationValidationStatus,
)


class AssessmentRepository(Protocol):
    async def add(self, assessment: Assessment) -> None: ...

    async def get(self, assessment_id: UUID) -> Assessment | None: ...


class IndicatorObservationRepository(Protocol):
    async def add(self, observation: IndicatorObservation) -> None: ...

    async def get_for_assessment(
        self,
        *,
        assessment_id: UUID,
        observation_id: UUID,
    ) -> IndicatorObservation | None: ...

    async def list_for_assessment(
        self,
        assessment_id: UUID,
    ) -> list[IndicatorObservation]: ...


class ObservationValidationRepository(Protocol):
    async def create_initial(
        self,
        state: ObservationValidationState,
    ) -> None: ...

    async def get_state(
        self,
        observation_id: UUID,
    ) -> ObservationValidationState | None: ...

    async def transition(
        self,
        *,
        previous: ObservationValidationState,
        current: ObservationValidationState,
    ) -> None: ...

    async def count_unresolved_for_assessment(
        self,
        assessment_id: UUID,
    ) -> int: ...


class AcceptedObservationRepository(Protocol):
    async def get(
        self,
        *,
        assessment_id: UUID,
        indicator_definition_id: UUID,
    ) -> AcceptedIndicatorObservation | None: ...

    async def list_for_assessment(
        self,
        assessment_id: UUID,
    ) -> list[AcceptedIndicatorObservation]: ...

    async def set_current(
        self,
        *,
        accepted: AcceptedIndicatorObservation,
        previous_observation_id: UUID | None,
        reason_code: str,
        reason_text: str | None,
        event_id: UUID,
    ) -> None: ...
