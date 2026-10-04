from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.household.api import routes as household_routes
from hamoon.domains.household.domain.entities import Household, HouseholdStatus
from hamoon.domains.identity.domain.entities import ActorType
from hamoon.domains.intervention.domain.entities import (
    Intervention,
    InterventionStatus,
    InterventionType,
)
from hamoon.domains.operations.domain.entities import (
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)
from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.pgor.domain.engine import EBand, PBand, PGORSnapshotStatus, RBand
from hamoon.domains.pgor.domain.snapshots import PGORSnapshot

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD_ID = UUID("22222222-2222-2222-2222-222222222222")
ASSESSMENT_ID = UUID("33333333-3333-3333-3333-333333333333")
SNAPSHOT_ID = UUID("44444444-4444-4444-4444-444444444444")
INTERVENTION_ID = UUID("55555555-5555-5555-5555-555555555555")
PRESCRIPTION_ITEM_ID = UUID("66666666-6666-6666-6666-666666666666")
WORK_ITEM_ID = UUID("77777777-7777-7777-7777-777777777777")
DEFINITION_ID = UUID("88888888-8888-8888-8888-888888888888")
FORMULA_ID = UUID("99999999-9999-9999-9999-999999999999")


def _household() -> Household:
    return Household(
        id=HOUSEHOLD_ID,
        case_code="H-1405-21842",
        lifecycle_status=HouseholdStatus.ACTIVE,
        organizational_unit_id="unit-12",
        primary_caseworker_id=ACTOR_ID,
        version=3,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        created_by=ACTOR_ID,
    )


def _pgor() -> PGORSnapshot:
    return PGORSnapshot(
        id=SNAPSHOT_ID,
        household_id=HOUSEHOLD_ID,
        assessment_id=ASSESSMENT_ID,
        definition_version_id=DEFINITION_ID,
        formula_version_id=FORMULA_ID,
        engine_version="engine-v1",
        scoring_version="score-v1",
        status=PGORSnapshotStatus.OFFICIAL,
        p=Decimal("0.68"),
        g=Decimal("0.61"),
        o=Decimal("0.34"),
        r=Decimal("0.53"),
        e=Decimal("0.54"),
        bottleneck_variables=(PGORVariableCode.O,),
        e_band=EBand.SUPPORTED_EMPOWERMENT,
        p_band=PBand.DESIRABLE,
        r_band=RBand.ACCEPTABLE,
        completeness_ratio=Decimal("1"),
        data_quality_flags=(),
        input_fingerprint="fingerprint",
        calculated_at=datetime(2026, 9, 13, tzinfo=UTC),
        calculated_by=ACTOR_ID,
    )


def _intervention() -> Intervention:
    return Intervention(
        id=INTERVENTION_ID,
        household_id=HOUSEHOLD_ID,
        prescription_item_id=PRESCRIPTION_ITEM_ID,
        intervention_type=InterventionType.EMPLOYMENT,
        target_pgor_variable=PGORVariableCode.O,
        status=InterventionStatus.ACTIVE,
        started_at=datetime(2026, 9, 20, tzinfo=UTC),
        completed_at=None,
        owner_actor_id=ACTOR_ID,
    )


def _work_item() -> WorkItem:
    return WorkItem(
        id=WORK_ITEM_ID,
        household_id=HOUSEHOLD_ID,
        work_type=WorkItemType.REFERRAL_FOLLOWUP,
        resource_type="REFERRAL",
        resource_id=INTERVENTION_ID,
        title="پیگیری نتیجه ارجاع",
        reason="موعد پیگیری فرا رسیده است.",
        priority=70,
        status=WorkItemStatus.OPEN,
        version=1,
        due_at=datetime.now(UTC) + timedelta(days=1),
        assigned_actor_id=ACTOR_ID,
        policy_version="followup-v1",
        created_at=datetime(2026, 10, 1, tzinfo=UTC),
        created_by=ACTOR_ID,
    )


class Households:
    async def list_for_actor(
        self,
        *,
        actor_id: UUID,
        query: str | None,
        lifecycle_status: HouseholdStatus | None,
        limit: int,
    ) -> list[Household]:
        assert actor_id == ACTOR_ID
        assert query is None
        assert lifecycle_status is None
        assert limit == 100
        return [_household()]

    async def get(self, household_id: UUID) -> Household | None:
        return _household() if household_id == HOUSEHOLD_ID else None


class PGOR:
    async def list_latest_official_for_households(
        self,
        household_ids: list[UUID],
    ) -> dict[UUID, PGORSnapshot]:
        assert household_ids == [HOUSEHOLD_ID]
        return {HOUSEHOLD_ID: _pgor()}


class Interventions:
    async def list_current_for_households(
        self,
        household_ids: list[UUID],
    ) -> dict[UUID, Intervention]:
        assert household_ids == [HOUSEHOLD_ID]
        return {HOUSEHOLD_ID: _intervention()}


class WorkItems:
    async def list_next_for_households(
        self,
        *,
        actor_id: UUID,
        household_ids: list[UUID],
    ) -> dict[UUID, WorkItem]:
        assert actor_id == ACTOR_ID
        assert household_ids == [HOUSEHOLD_ID]
        return {HOUSEHOLD_ID: _work_item()}


def _context() -> AuthorizationContext:
    return AuthorizationContext(
        actor_id=ACTOR_ID,
        actor_type=ActorType.HUMAN,
        subject="caseworker",
        issuer="https://identity.local",
        roles=frozenset({Role.CASEWORKER}),
        scopes=frozenset(),
    )


def _patch_repositories(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        household_routes,
        "SqlAlchemyHouseholdRepository",
        lambda _session: Households(),
    )
    monkeypatch.setattr(
        household_routes,
        "SqlAlchemyPGORSnapshotRepository",
        lambda _session: PGOR(),
    )
    monkeypatch.setattr(
        household_routes,
        "SqlAlchemyInterventionRepository",
        lambda _session: Interventions(),
    )
    monkeypatch.setattr(
        household_routes,
        "SqlAlchemyWorkItemRepository",
        lambda _session: WorkItems(),
    )


@pytest.mark.asyncio
async def test_list_households_returns_caseworker_read_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_repositories(monkeypatch)

    response = await household_routes.list_households(
        _context(),
        cast(AsyncSession, object()),
        query=None,
        lifecycle_status=None,
        limit=100,
    )

    assert len(response.data) == 1
    item = response.data[0]
    assert item.case_code == "H-1405-21842"
    assert item.pgor is not None
    assert item.pgor.e == Decimal("0.54")
    assert item.pgor.bottleneck_variables == [PGORVariableCode.O]
    assert item.current_intervention is not None
    assert item.current_intervention.status is InterventionStatus.ACTIVE
    assert item.next_work_item is not None
    assert item.next_work_item.work_type is WorkItemType.REFERRAL_FOLLOWUP


@pytest.mark.asyncio
async def test_get_household_requires_assignment_and_returns_same_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_repositories(monkeypatch)
    scoped: list[UUID] = []

    async def require_scope(
        *,
        session: AsyncSession,
        context: AuthorizationContext,
        household_id: UUID,
    ) -> None:
        del session, context
        scoped.append(household_id)

    monkeypatch.setattr(
        household_routes,
        "require_household_assignment",
        require_scope,
    )

    response = await household_routes.get_household(
        HOUSEHOLD_ID,
        _context(),
        cast(AsyncSession, object()),
    )

    assert scoped == [HOUSEHOLD_ID]
    assert response.data.id == HOUSEHOLD_ID
    assert response.data.pgor is not None
    assert response.data.pgor.assessment_id == ASSESSMENT_ID
    assert response.data.next_work_item is not None
    assert response.data.next_work_item.id == WORK_ITEM_ID
