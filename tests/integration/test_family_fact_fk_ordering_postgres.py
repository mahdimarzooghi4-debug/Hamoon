"""Regression for FK ordering in the real PostgreSQL fact/validation persistence path."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from hamoon.app.config.settings import get_settings
from hamoon.domains.family_data.domain.entities import (
    FactValidationState, FactValidationStatus, FactValueType, HouseholdFact, SourceType,
)
from hamoon.domains.family_data.infrastructure.models import (
    DataSourceModel, FactValidationChangeModel, FactValidationStateModel, HouseholdFactModel,
)
from hamoon.domains.family_data.infrastructure.repositories import (
    SqlAlchemyFactValidationRepository, SqlAlchemyHouseholdFactRepository,
)
from hamoon.domains.household.domain.entities import HouseholdStatus
from hamoon.domains.household.infrastructure.models import HouseholdModel
from hamoon.domains.identity.domain.entities import ActorStatus, ActorType
from hamoon.domains.identity.infrastructure.models import ActorModel


@pytest.mark.asyncio
async def test_fact_parent_flushes_before_initial_validation_history() -> None:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor_id, household_id, source_id, fact_id = (uuid4() for _ in range(4))
    now = datetime.now(UTC)
    try:
        async with sessions() as session:
            async with session.begin():
                session.add(ActorModel(
                    id=actor_id, actor_type=ActorType.HUMAN, display_name="Synthetic FK QA",
                    status=ActorStatus.ACTIVE, created_at=now,
                ))
                await session.flush()
                session.add(HouseholdModel(
                    id=household_id, case_code=f"QA-FK-{household_id.hex[:12]}",
                    lifecycle_status=HouseholdStatus.DRAFT,
                    organizational_unit_id="integration", primary_caseworker_id=actor_id,
                    version=1, created_at=now, created_by=actor_id, closed_at=None,
                ))
                session.add(DataSourceModel(
                    id=source_id, code=f"QA-FK-{source_id.hex[:12]}",
                    source_type=SourceType.HOUSEHOLD_DECLARATION,
                    name="Synthetic FK QA source", active=True,
                ))
        async with sessions() as session:
            async with session.begin():
                await SqlAlchemyHouseholdFactRepository(session).add(HouseholdFact(
                    id=fact_id, household_id=household_id, fact_type="QA_FK",
                    value_type=FactValueType.CODE, value="SYNTHETIC", source_id=source_id,
                    effective_from=now, recorded_at=now, recorded_by=actor_id,
                ))
                await SqlAlchemyFactValidationRepository(session).create_initial(
                    state=FactValidationState(
                        fact_id=fact_id, status=FactValidationStatus.PENDING_VALIDATION,
                        version=1, changed_at=now, changed_by=actor_id,
                        reason_code="FACT_RECORDED",
                    ), occurred_at=now,
                )
                # Mirrors the handler's next query, which previously triggered
                # an autoflush of validation history before its fact parent.
                await session.execute(select(FactValidationChangeModel))
        async with sessions() as session:
            assert await session.get(HouseholdFactModel, fact_id) is not None
            state = await session.get(FactValidationStateModel, fact_id)
            assert state is not None
            assert state.status is FactValidationStatus.PENDING_VALIDATION
            changes = (await session.execute(
                select(FactValidationChangeModel).where(
                    FactValidationChangeModel.fact_id == fact_id
                )
            )).scalars().all()
            assert len(changes) == 1
            assert changes[0].validation_version == 1
    finally:
        await engine.dispose()
