from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from hamoon.domains.assessment.application.handlers import EvaluateAssessmentReadinessHandler
from hamoon.domains.assessment.domain.entities import (
    AcceptedIndicatorObservation,
    Assessment,
    AssessmentReadinessStatus,
    AssessmentStatus,
    AssessmentType,
)
from hamoon.domains.pgor.domain.definitions import (
    PGORDefinitionStatus,
    PGORDefinitionVersion,
    PGORIndicatorDefinition,
    RequirementPolicyStatus,
)

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD_ID = UUID("22222222-2222-2222-2222-222222222222")
ASSESSMENT_ID = UUID("33333333-3333-3333-3333-333333333333")
DEFINITION_ID = UUID("44444444-4444-4444-4444-444444444444")
DIMENSION_ID = UUID("55555555-5555-5555-5555-555555555555")
INDICATOR_A = UUID("66666666-6666-6666-6666-666666666661")
INDICATOR_B = UUID("66666666-6666-6666-6666-666666666662")
OBS_A = UUID("77777777-7777-7777-7777-777777777771")
OBS_B = UUID("77777777-7777-7777-7777-777777777772")


class AssessmentRepo:
    async def add(self, assessment: Assessment) -> None:
        pass

    async def get(self, assessment_id: UUID):
        if assessment_id != ASSESSMENT_ID:
            return None
        return Assessment(
            id=ASSESSMENT_ID,
            household_id=HOUSEHOLD_ID,
            assessment_type=AssessmentType.BASELINE,
            definition_version_id=DEFINITION_ID,
            status=AssessmentStatus.IN_PROGRESS,
            version=1,
            started_at=datetime.now(UTC),
            started_by=ACTOR_ID,
        )


class DefinitionRepo:
    def __init__(self, policy_status: RequirementPolicyStatus) -> None:
        self.policy_status = policy_status

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
            requirement_policy_status=self.policy_status,
            source_reference="source",
        )

    async def list_indicators(self, definition_version_id: UUID):
        return [
            PGORIndicatorDefinition(
                id=INDICATOR_A,
                dimension_definition_id=DIMENSION_ID,
                code="a",
                name_fa="الف",
                score_min=0,
                score_max=100,
                required_for_complete_assessment=True,
                direct_dimension_measure=False,
                sort_order=1,
            ),
            PGORIndicatorDefinition(
                id=INDICATOR_B,
                dimension_definition_id=DIMENSION_ID,
                code="b",
                name_fa="ب",
                score_min=0,
                score_max=100,
                required_for_complete_assessment=True,
                direct_dimension_measure=False,
                sort_order=2,
            ),
        ]

    async def get_indicator(self, *, definition_version_id: UUID, indicator_id: UUID):
        for indicator in await self.list_indicators(definition_version_id):
            if indicator.id == indicator_id:
                return indicator
        return None


class AcceptedRepo:
    def __init__(self, items: list[AcceptedIndicatorObservation]) -> None:
        self.items = items

    async def get(self, *, assessment_id: UUID, indicator_definition_id: UUID):
        return next(
            (
                item
                for item in self.items
                if item.assessment_id == assessment_id
                and item.indicator_definition_id == indicator_definition_id
            ),
            None,
        )

    async def list_for_assessment(self, assessment_id: UUID):
        return [item for item in self.items if item.assessment_id == assessment_id]

    async def set_current(self, **kwargs) -> None:
        pass


class ValidationRepo:
    async def create_initial(self, state) -> None:
        pass

    async def get_state(self, observation_id: UUID):
        return None

    async def transition(self, *, previous, current) -> None:
        pass

    async def count_unresolved_for_assessment(self, assessment_id: UUID) -> int:
        return 0


def accepted(indicator_id: UUID, observation_id: UUID) -> AcceptedIndicatorObservation:
    return AcceptedIndicatorObservation(
        assessment_id=ASSESSMENT_ID,
        indicator_definition_id=indicator_id,
        observation_id=observation_id,
        projection_version=1,
        changed_at=datetime.now(UTC),
        changed_by=ACTOR_ID,
    )


@pytest.mark.asyncio
async def test_source_seed_blocks_official_readiness_until_requirement_policy_is_approved() -> None:
    result = await EvaluateAssessmentReadinessHandler(
        assessments=AssessmentRepo(),
        definitions=DefinitionRepo(RequirementPolicyStatus.UNRESOLVED),
        accepted_observations=AcceptedRepo([]),
        validations=ValidationRepo(),
    ).handle(ASSESSMENT_ID)

    assert result.status is AssessmentReadinessStatus.REQUIREMENT_POLICY_UNRESOLVED
    assert result.completeness_ratio is None
    assert result.blocking_reasons == ("REQUIREMENT_POLICY_UNRESOLVED",)


@pytest.mark.asyncio
async def test_resolved_requirement_policy_reports_missing_required_indicator() -> None:
    result = await EvaluateAssessmentReadinessHandler(
        assessments=AssessmentRepo(),
        definitions=DefinitionRepo(RequirementPolicyStatus.RESOLVED),
        accepted_observations=AcceptedRepo([accepted(INDICATOR_A, OBS_A)]),
        validations=ValidationRepo(),
    ).handle(ASSESSMENT_ID)

    assert result.status is AssessmentReadinessStatus.INCOMPLETE
    assert result.required_indicator_count == 2
    assert result.accepted_required_indicator_count == 1
    assert result.completeness_ratio == Decimal("0.5")
    assert result.missing_required_indicator_ids == (INDICATOR_B,)


@pytest.mark.asyncio
async def test_resolved_requirement_policy_is_ready_when_all_required_are_accepted() -> None:
    result = await EvaluateAssessmentReadinessHandler(
        assessments=AssessmentRepo(),
        definitions=DefinitionRepo(RequirementPolicyStatus.RESOLVED),
        accepted_observations=AcceptedRepo(
            [
                accepted(INDICATOR_A, OBS_A),
                accepted(INDICATOR_B, OBS_B),
            ]
        ),
        validations=ValidationRepo(),
    ).handle(ASSESSMENT_ID)

    assert result.status is AssessmentReadinessStatus.READY
    assert result.completeness_ratio == Decimal("1")
