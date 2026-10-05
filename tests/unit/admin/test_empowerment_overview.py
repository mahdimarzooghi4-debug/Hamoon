from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.admin.api import routes as admin_routes
from hamoon.domains.admin.infrastructure.empowerment import (
    EmpowermentOverview,
    VariableDistribution,
)
from hamoon.domains.identity.domain.entities import ActorType
from hamoon.domains.outcome.domain.entities import OutcomeClassification
from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.pgor.domain.engine import EBand


def _context(*, unit_id: str | None) -> AuthorizationContext:
    return AuthorizationContext(
        actor_id=uuid4(),
        actor_type=ActorType.HUMAN,
        subject="manager",
        issuer="test",
        roles=frozenset({Role.MANAGER}),
        scopes=frozenset(),
        unit_id=unit_id,
    )


def test_empowerment_overview_requires_unit_scope() -> None:
    with pytest.raises(HTTPException) as exc_info:
        admin_routes._require_empowerment_unit_scope(
            _context(unit_id=None)
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == {
        "code": "ANALYTICS_UNIT_SCOPE_REQUIRED"
    }


@pytest.mark.asyncio
async def test_empowerment_overview_returns_only_scoped_aggregate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_units: list[str] = []

    class Repository:
        def __init__(self, _session: AsyncSession) -> None:
            pass

        async def get_for_unit(self, *, unit_id: str) -> EmpowermentOverview:
            requested_units.append(unit_id)
            distribution = VariableDistribution(
                mean=Decimal("0.5"),
                minimum=Decimal("0.2"),
                maximum=Decimal("0.8"),
            )
            return EmpowermentOverview(
                household_count=12,
                households_with_official_pgor=9,
                p=distribution,
                g=distribution,
                o=distribution,
                r=distribution,
                e=distribution,
                e_band_counts={
                    EBand.SEVERE_CRISIS: 1,
                    EBand.VULNERABLE: 2,
                    EBand.SUPPORTED_EMPOWERMENT: 4,
                    EBand.ECONOMIC_SOCIAL_INDEPENDENCE: 2,
                },
                bottleneck_counts={
                    PGORVariableCode.P: 2,
                    PGORVariableCode.G: 3,
                    PGORVariableCode.O: 1,
                    PGORVariableCode.R: 4,
                },
                outcome_counts={
                    OutcomeClassification.GOAL_ACHIEVED: 2,
                    OutcomeClassification.PROGRESS: 3,
                    OutcomeClassification.NO_SIGNIFICANT_CHANGE: 1,
                    OutcomeClassification.REGRESSION: 1,
                    OutcomeClassification.NEEDS_MORE_TIME: 2,
                    OutcomeClassification.NEEDS_MORE_DATA: 0,
                },
                unreviewed_outcomes=1,
            )

    monkeypatch.setattr(
        admin_routes,
        "SqlAlchemyEmpowermentOverviewRepository",
        Repository,
    )

    response = await admin_routes.get_empowerment_overview(
        _context(unit_id="unit-a"),
        cast(AsyncSession, object()),
    )

    assert requested_units == ["unit-a"]
    assert response.data.scope_unit_id == "unit-a"
    assert response.data.household_count == 12
    assert response.data.households_with_official_pgor == 9
    assert response.data.e_band_counts[EBand.SUPPORTED_EMPOWERMENT] == 4
    assert response.data.bottleneck_counts[PGORVariableCode.R] == 4
    assert response.data.outcome_counts[OutcomeClassification.PROGRESS] == 3
