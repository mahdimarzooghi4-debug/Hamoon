from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from hamoon.domains.assessment.application.commands import (
    ChangeObservationValidationCommand,
    RecordIndicatorObservationCommand,
    ResolveAcceptedObservationCommand,
)
from hamoon.domains.assessment.application.handlers import (
    ChangeObservationValidationHandler,
    RecordIndicatorObservationHandler,
    ResolveAcceptedObservationHandler,
)
from hamoon.domains.assessment.domain.entities import (
    AcceptedIndicatorObservation,
    Assessment,
    AssessmentStatus,
    AssessmentType,
    IndicatorObservation,
    ObservationValidationState,
    ObservationValidationStatus,
)
from hamoon.domains.assessment.domain.errors import ObservationNotValidatedError
from hamoon.domains.family_data.domain.entities import DataSource, SourceType
from hamoon.domains.pgor.domain.definitions import (
    PGORDefinitionStatus,
    PGORDefinitionVersion,
    PGORIndicatorDefinition,
    RequirementPolicyStatus,
)
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD_ID = UUID("22222222-2222-2222-2222-222222222222")
ASSESSMENT_ID = UUID("33333333-3333-3333-3333-333333333333")
DEFINITION_ID = UUID("44444444-4444-4444-4444-444444444444")
INDICATOR_ID = UUID("55555555-5555-5555-5555-555555555555")
DIMENSION_ID = UUID("66666666-6666-6666-6666-666666666666")
SOURCE_ID = UUID("00000000-0000-0000-0000-000000000101")


class FakeAssessmentRepository:
    def __init__(self) -> None:
        self.item = Assessment(
            id=ASSESSMENT_ID,
            household_id=HOUSEHOLD_ID,
            assessment_type=AssessmentType.BASELINE,
            definition_version_id=DEFINITION_ID,
            status=AssessmentStatus.IN_PROGRESS,
            version=1,
            started_at=datetime.now(UTC),
            started_by=ACTOR_ID,
        )

    async def add(self, assessment: Assessment) -> None:
        self.item = assessment

    async def get(self, assessment_id: UUID) -> Assessment | None:
        return self.item if assessment_id == self.item.id else None


class FakeDefinitionRepository:
    async def get_active_bundle(self):
        return None

    async def get_version(self, definition_version_id: UUID):
        if definition_version_id != DEFINITION_ID:
            return None
        return PGORDefinitionVersion(
            id=DEFINITION_ID,
            code="pgor-v1",
            version="1.0.0",
            status=PGORDefinitionStatus.ACTIVE,
            requirement_policy_status=RequirementPolicyStatus.UNRESOLVED,
            source_reference="source",
        )

    async def list_indicators(self, definition_version_id: UUID):
        return [await self.get_indicator(
            definition_version_id=definition_version_id,
            indicator_id=INDICATOR_ID,
        )]

    async def get_indicator(
        self,
        *,
        definition_version_id: UUID,
        indicator_id: UUID,
    ):
        if definition_version_id != DEFINITION_ID or indicator_id != INDICATOR_ID:
            return None
        return PGORIndicatorDefinition(
            id=INDICATOR_ID,
            dimension_definition_id=DIMENSION_ID,
            code="willingness_to_change",
            name_fa="تمایل به تغییر",
            score_min=0,
            score_max=100,
            required_for_complete_assessment=None,
            direct_dimension_measure=False,
            sort_order=1,
        )


class FakeSourceRepository:
    async def get(self, source_id: UUID):
        if source_id != SOURCE_ID:
            return None
        return DataSource(
            id=SOURCE_ID,
            code="HOUSEHOLD_DECLARATION",
            source_type=SourceType.HOUSEHOLD_DECLARATION,
            name="خوداظهاری خانوار",
            active=True,
        )

    async def list_active(self):
        source = await self.get(SOURCE_ID)
        return [] if source is None else [source]


class FakeObservationRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, IndicatorObservation] = {}

    async def add(self, observation: IndicatorObservation) -> None:
        self.items[observation.id] = observation

    async def get_for_assessment(self, *, assessment_id: UUID, observation_id: UUID):
        item = self.items.get(observation_id)
        return item if item and item.assessment_id == assessment_id else None

    async def list_for_assessment(self, assessment_id: UUID):
        return [item for item in self.items.values() if item.assessment_id == assessment_id]


class FakeValidationRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, ObservationValidationState] = {}

    async def create_initial(self, state: ObservationValidationState) -> None:
        self.items[state.observation_id] = state

    async def get_state(self, observation_id: UUID):
        return self.items.get(observation_id)

    async def transition(self, *, previous, current) -> None:
        self.items[current.observation_id] = current

    async def count_unresolved_for_assessment(self, assessment_id: UUID) -> int:
        return sum(
            1
            for state in self.items.values()
            if state.status
            in {
                ObservationValidationStatus.PENDING_VALIDATION,
                ObservationValidationStatus.DISPUTED,
            }
        )


class FakeAcceptedRepository:
    def __init__(self) -> None:
        self.items: dict[tuple[UUID, UUID], AcceptedIndicatorObservation] = {}

    async def get(self, *, assessment_id: UUID, indicator_definition_id: UUID):
        return self.items.get((assessment_id, indicator_definition_id))

    async def list_for_assessment(self, assessment_id: UUID):
        return [
            item
            for (aid, _), item in self.items.items()
            if aid == assessment_id
        ]

    async def set_current(
        self,
        *,
        accepted,
        previous_observation_id,
        reason_code,
        reason_text,
        event_id,
    ) -> None:
        self.items[
            (accepted.assessment_id, accepted.indicator_definition_id)
        ] = accepted


class FakeEventRecorder:
    def __init__(self) -> None:
        self.items: list[DomainEventRecord] = []

    async def record(self, event: DomainEventRecord) -> None:
        self.items.append(event)


class FakeAuditRecorder:
    def __init__(self) -> None:
        self.items: list[AuditRecord] = []

    async def record(self, audit: AuditRecord) -> None:
        self.items.append(audit)


@pytest.mark.asyncio
async def test_observation_starts_pending_and_requires_validation_before_acceptance() -> None:
    observations = FakeObservationRepository()
    validations = FakeValidationRepository()
    accepted = FakeAcceptedRepository()
    events = FakeEventRecorder()
    audits = FakeAuditRecorder()

    observation, validation = await RecordIndicatorObservationHandler(
        assessments=FakeAssessmentRepository(),
        definitions=FakeDefinitionRepository(),
        sources=FakeSourceRepository(),
        observations=observations,
        validations=validations,
        events=events,
        audits=audits,
    ).handle(
        RecordIndicatorObservationCommand(
            assessment_id=ASSESSMENT_ID,
            actor_id=ACTOR_ID,
            indicator_definition_id=INDICATOR_ID,
            raw_score_0_100=Decimal("60"),
            source_id=SOURCE_ID,
            source_detail=None,
            effective_at=datetime.now(UTC),
            request_id="req-1",
            correlation_id="corr-1",
        )
    )

    assert validation.status is ObservationValidationStatus.PENDING_VALIDATION

    resolve = ResolveAcceptedObservationHandler(
        observations=observations,
        validations=validations,
        accepted_observations=accepted,
        events=events,
        audits=audits,
    )
    with pytest.raises(ObservationNotValidatedError):
        await resolve.handle(
            ResolveAcceptedObservationCommand(
                assessment_id=ASSESSMENT_ID,
                indicator_definition_id=INDICATOR_ID,
                observation_id=observation.id,
                actor_id=ACTOR_ID,
                expected_projection_version=0,
                reason_code="HUMAN_RESOLUTION",
                reason_text=None,
                request_id="req-2",
                correlation_id="corr-1",
            )
        )

    validated = await ChangeObservationValidationHandler(
        observations=observations,
        validations=validations,
        events=events,
        audits=audits,
    ).handle(
        ChangeObservationValidationCommand(
            assessment_id=ASSESSMENT_ID,
            observation_id=observation.id,
            actor_id=ACTOR_ID,
            to_status=ObservationValidationStatus.VALIDATED,
            expected_validation_version=1,
            reason_code="SOURCE_REVIEWED",
            reason_text=None,
            request_id="req-3",
            correlation_id="corr-1",
        )
    )
    assert validated.status is ObservationValidationStatus.VALIDATED

    projection = await resolve.handle(
        ResolveAcceptedObservationCommand(
            assessment_id=ASSESSMENT_ID,
            indicator_definition_id=INDICATOR_ID,
            observation_id=observation.id,
            actor_id=ACTOR_ID,
            expected_projection_version=0,
            reason_code="HUMAN_RESOLUTION",
            reason_text=None,
            request_id="req-4",
            correlation_id="corr-1",
        )
    )
    assert projection.observation_id == observation.id
    assert events.items[-1].event_type == "AssessmentAcceptedObservationChanged"
