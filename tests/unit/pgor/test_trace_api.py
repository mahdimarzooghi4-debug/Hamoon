from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.identity.domain.entities import ActorType
from hamoon.domains.pgor.api import routes as pgor_routes
from hamoon.domains.pgor.domain.definitions import PGORVariableCode

ACTOR_ID = UUID(int=1)
HOUSEHOLD_ID = UUID(int=2)
SNAPSHOT_ID = UUID(int=3)
ASSESSMENT_ID = UUID(int=4)
DEFINITION_ID = UUID(int=5)
FORMULA_ID = UUID(int=6)
P_VARIABLE_ID = UUID(int=7)
G_VARIABLE_ID = UUID(int=8)
P_DIMENSION_ID = UUID(int=9)
G_DIMENSION_ID = UUID(int=10)
P_INDICATOR_ID = UUID(int=11)
G_INDICATOR_ID = UUID(int=12)
P_OBSERVATION_ID = UUID(int=13)
G_OBSERVATION_ID = UUID(int=14)


class Snapshots:
    async def get(self, snapshot_id: UUID) -> SimpleNamespace | None:
        if snapshot_id != SNAPSHOT_ID:
            return None
        return SimpleNamespace(
            id=SNAPSHOT_ID,
            household_id=HOUSEHOLD_ID,
            assessment_id=ASSESSMENT_ID,
            definition_version_id=DEFINITION_ID,
            formula_version_id=FORMULA_ID,
            engine_version="engine-v1",
            scoring_version="score-v1",
            input_fingerprint="f" * 64,
            calculated_at=datetime(2026, 10, 5, tzinfo=UTC),
        )

    async def list_inputs(self, snapshot_id: UUID) -> list[SimpleNamespace]:
        assert snapshot_id == SNAPSHOT_ID
        return [
            SimpleNamespace(
                observation_id=G_OBSERVATION_ID,
                observation_version=3,
                indicator_definition_id=G_INDICATOR_ID,
                dimension_definition_id=G_DIMENSION_ID,
                variable_code=PGORVariableCode.G,
                raw_score_0_100=Decimal("73.00"),
                normalized_score=Decimal("0.7300"),
            ),
            SimpleNamespace(
                observation_id=P_OBSERVATION_ID,
                observation_version=2,
                indicator_definition_id=P_INDICATOR_ID,
                dimension_definition_id=P_DIMENSION_ID,
                variable_code=PGORVariableCode.P,
                raw_score_0_100=Decimal("41.00"),
                normalized_score=Decimal("0.4100"),
            ),
        ]


class Definitions:
    async def get_bundle(self, definition_version_id: UUID) -> SimpleNamespace:
        assert definition_version_id == DEFINITION_ID
        return SimpleNamespace(
            version=SimpleNamespace(version="pgor-v1"),
            variables=(
                SimpleNamespace(code=PGORVariableCode.P, sort_order=1),
                SimpleNamespace(code=PGORVariableCode.G, sort_order=2),
            ),
            dimensions=(
                SimpleNamespace(
                    id=P_DIMENSION_ID,
                    code="P-D1",
                    name_fa="بعد مشارکت",
                    sort_order=1,
                ),
                SimpleNamespace(
                    id=G_DIMENSION_ID,
                    code="G-D1",
                    name_fa="بعد رشد",
                    sort_order=1,
                ),
            ),
            indicators=(
                SimpleNamespace(
                    id=P_INDICATOR_ID,
                    code="P-I1",
                    name_fa="شاخص مشارکت",
                    sort_order=1,
                ),
                SimpleNamespace(
                    id=G_INDICATOR_ID,
                    code="G-I1",
                    name_fa="شاخص رشد",
                    sort_order=1,
                ),
            ),
        )


def _context() -> AuthorizationContext:
    return AuthorizationContext(
        actor_id=ACTOR_ID,
        actor_type=ActorType.HUMAN,
        subject="caseworker",
        issuer="test",
        roles=frozenset({Role.CASEWORKER}),
        scopes=frozenset(),
    )


@pytest.mark.asyncio
async def test_snapshot_trace_reads_persisted_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        pgor_routes,
        "SqlAlchemyPGORSnapshotRepository",
        lambda _session: Snapshots(),
    )
    monkeypatch.setattr(
        pgor_routes,
        "SqlAlchemyPGORDefinitionRepository",
        lambda _session: Definitions(),
    )
    monkeypatch.setattr(
        pgor_routes,
        "require_household_assignment",
        require_scope,
    )

    response = await pgor_routes.get_snapshot_trace(
        SNAPSHOT_ID,
        _context(),
        cast(AsyncSession, object()),
    )

    assert scoped == [HOUSEHOLD_ID]
    assert response.data.definition_version == "pgor-v1"
    assert response.data.input_fingerprint == "f" * 64
    assert [item.variable_code for item in response.data.inputs] == [
        PGORVariableCode.P,
        PGORVariableCode.G,
    ]

    first = response.data.inputs[0]
    assert first.observation_id == P_OBSERVATION_ID
    assert first.observation_version == 2
    assert first.indicator_code == "P-I1"
    assert first.dimension_code == "P-D1"
    assert first.raw_score_0_100 == Decimal("41.00")
    assert first.normalized_score == Decimal("0.4100")
