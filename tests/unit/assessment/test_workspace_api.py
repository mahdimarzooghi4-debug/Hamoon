from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.assessment.api import routes as assessment_routes
from hamoon.domains.assessment.domain.entities import (
    AcceptedIndicatorObservation,
    Assessment,
    AssessmentStatus,
    AssessmentType,
    IndicatorObservation,
    ObservationValidationState,
    ObservationValidationStatus,
)
from hamoon.domains.identity.domain.entities import ActorType
from hamoon.domains.pgor.domain.definitions import (
    PGORDefinitionBundle,
    PGORDefinitionStatus,
    PGORDefinitionVersion,
    PGORDimensionDefinition,
    PGORIndicatorDefinition,
    PGORVariableCode,
    PGORVariableDefinition,
    RequirementPolicyStatus,
)

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD_ID = UUID("22222222-2222-2222-2222-222222222222")
ASSESSMENT_ID = UUID("33333333-3333-3333-3333-333333333333")
DEFINITION_ID = UUID("44444444-4444-4444-4444-444444444444")
VARIABLE_ID = UUID("55555555-5555-5555-5555-555555555555")
DIMENSION_ID = UUID("66666666-6666-6666-6666-666666666666")
INDICATOR_ID = UUID("77777777-7777-7777-7777-777777777777")
OBSERVATION_ID = UUID("88888888-8888-8888-8888-888888888888")
SOURCE_ID = UUID("99999999-9999-9999-9999-999999999999")


def _context() -> AuthorizationContext:
    return AuthorizationContext(
        actor_id=ACTOR_ID,
        actor_type=ActorType.HUMAN,
        subject="caseworker",
        issuer="https://identity.local",
        roles=frozenset({Role.CASEWORKER}),
        scopes=frozenset(),
    )


def _assessment() -> Assessment:
    return Assessment(
        id=ASSESSMENT_ID,
        household_id=HOUSEHOLD_ID,
        assessment_type=AssessmentType.OUTCOME_REASSESSMENT,
        definition_version_id=DEFINITION_ID,
        status=AssessmentStatus.IN_PROGRESS,
        version=1,
        started_at=datetime(2026, 10, 4, 10, 0, tzinfo=UTC),
        started_by=ACTOR_ID,
        reason="scheduled reassessment",
    )


def _bundle() -> PGORDefinitionBundle:
    return PGORDefinitionBundle(
        version=PGORDefinitionVersion(
            id=DEFINITION_ID,
            code="PGOR",
            version="v3",
            status=PGORDefinitionStatus.ACTIVE,
            requirement_policy_status=RequirementPolicyStatus.RESOLVED,
            source_reference="policy://pgor/v3",
        ),
        variables=(
            PGORVariableDefinition(
                id=VARIABLE_ID,
                definition_version_id=DEFINITION_ID,
                code=PGORVariableCode.O,
                name_fa="فرصت",
                sort_order=3,
            ),
        ),
        dimensions=(
            PGORDimensionDefinition(
                id=DIMENSION_ID,
                variable_definition_id=VARIABLE_ID,
                code="EMPLOYMENT_OPPORTUNITY",
                name_fa="فرصت اشتغال",
                sort_order=1,
            ),
        ),
        indicators=(
            PGORIndicatorDefinition(
                id=INDICATOR_ID,
                dimension_definition_id=DIMENSION_ID,
                code="JOB_ACCESS",
                name_fa="دسترسی به فرصت شغلی",
                score_min=0,
                score_max=100,
                required_for_complete_assessment=True,
                direct_dimension_measure=True,
                sort_order=1,
            ),
        ),
    )


def _observation() -> IndicatorObservation:
    return IndicatorObservation(
        id=OBSERVATION_ID,
        assessment_id=ASSESSMENT_ID,
        indicator_definition_id=INDICATOR_ID,
        raw_score_0_100=Decimal("72.00"),
        source_id=SOURCE_ID,
        source_detail="مصاحبه بازسنجی",
        effective_at=datetime(2026, 10, 4, 9, 45, tzinfo=UTC),
        observed_at=datetime(2026, 10, 4, 10, 5, tzinfo=UTC),
        observed_by=ACTOR_ID,
    )


class Assessments:
    async def get(self, assessment_id: UUID) -> Assessment | None:
        return _assessment() if assessment_id == ASSESSMENT_ID else None


class Definitions:
    async def get_bundle(self, definition_version_id: UUID) -> PGORDefinitionBundle | None:
        assert definition_version_id == DEFINITION_ID
        return _bundle()


class Observations:
    async def list_for_assessment(
        self,
        assessment_id: UUID,
    ) -> list[IndicatorObservation]:
        assert assessment_id == ASSESSMENT_ID
        return [_observation()]


class Validations:
    async def list_states_for_observations(
        self,
        observation_ids: list[UUID],
    ) -> dict[UUID, ObservationValidationState]:
        assert observation_ids == [OBSERVATION_ID]
        return {
            OBSERVATION_ID: ObservationValidationState(
                observation_id=OBSERVATION_ID,
                status=ObservationValidationStatus.VALIDATED,
                version=2,
                changed_at=datetime(2026, 10, 4, 10, 10, tzinfo=UTC),
                changed_by=ACTOR_ID,
                reason_code="CASEWORKER_VALIDATED",
            )
        }


class Accepted:
    async def list_for_assessment(
        self,
        assessment_id: UUID,
    ) -> list[AcceptedIndicatorObservation]:
        assert assessment_id == ASSESSMENT_ID
        return [
            AcceptedIndicatorObservation(
                assessment_id=ASSESSMENT_ID,
                indicator_definition_id=INDICATOR_ID,
                observation_id=OBSERVATION_ID,
                projection_version=1,
                changed_at=datetime(2026, 10, 4, 10, 12, tzinfo=UTC),
                changed_by=ACTOR_ID,
            )
        ]


@pytest.mark.asyncio
async def test_assessment_workspace_returns_definition_and_latest_accepted_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def require_scope(
        *,
        session: AsyncSession,
        context: AuthorizationContext,
        household_id: UUID,
    ) -> None:
        del session, context
        assert household_id == HOUSEHOLD_ID

    monkeypatch.setattr(
        assessment_routes,
        "SqlAlchemyAssessmentRepository",
        lambda _session: Assessments(),
    )
    monkeypatch.setattr(
        assessment_routes,
        "SqlAlchemyPGORDefinitionRepository",
        lambda _session: Definitions(),
    )
    monkeypatch.setattr(
        assessment_routes,
        "SqlAlchemyIndicatorObservationRepository",
        lambda _session: Observations(),
    )
    monkeypatch.setattr(
        assessment_routes,
        "SqlAlchemyObservationValidationRepository",
        lambda _session: Validations(),
    )
    monkeypatch.setattr(
        assessment_routes,
        "SqlAlchemyAcceptedObservationRepository",
        lambda _session: Accepted(),
    )
    monkeypatch.setattr(
        assessment_routes,
        "require_household_assignment",
        require_scope,
    )

    response = await assessment_routes.get_assessment_workspace(
        ASSESSMENT_ID,
        _context(),
        cast(AsyncSession, object()),
    )

    assert response.data.definition_code == "PGOR"
    assert response.data.definition_version == "v3"
    assert len(response.data.indicators) == 1
    indicator = response.data.indicators[0]
    assert indicator.variable_code == "O"
    assert indicator.variable_name_fa == "فرصت"
    assert indicator.dimension_name_fa == "فرصت اشتغال"
    assert indicator.name_fa == "دسترسی به فرصت شغلی"
    assert indicator.latest_observation is not None
    assert indicator.latest_observation.raw_score_0_100 == Decimal("72.00")
    assert indicator.latest_observation.validation_status is ObservationValidationStatus.VALIDATED
    assert indicator.latest_observation.accepted is True
    assert indicator.latest_observation.accepted_projection_version == 1
