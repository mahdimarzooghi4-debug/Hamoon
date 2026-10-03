from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from hamoon.app.config.settings import get_settings
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.admin.api.routes import get_data_health, get_machine_health
from hamoon.domains.identity.domain.entities import ActorType


@pytest.mark.asyncio
async def test_admin_health_projections_execute_on_real_postgres() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    context = AuthorizationContext(
        actor_id=uuid4(),
        actor_type=ActorType.HUMAN,
        subject="integration-admin",
        issuer="integration",
        roles=frozenset({Role.ADMIN}),
        scopes=frozenset(),
    )

    async with session_maker() as session:
        data = await get_data_health(context, session)
        machine = await get_machine_health(context, session)

    assert data.data.pending_validation_facts >= 0
    assert data.data.pending_outbox_messages >= 0
    assert data.data.quarantined_evidence >= 0
    assert machine.data.ai_decisions_total >= 0
    assert machine.data.learning_signal_raw >= 0
    assert machine.data.evaluation_pending >= 0
    assert machine.data.active_routing_policies >= 0

    await engine.dispose()
