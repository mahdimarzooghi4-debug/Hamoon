from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from hamoon.app.config.settings import get_settings
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.domains.admin.api.routes import get_data_health, get_machine_health
from hamoon.domains.identity.domain.entities import ActorType
from hamoon.app.observability.heartbeats import (
    read_operational_snapshot,
    record_worker_heartbeat,
)
from hamoon.infrastructure.db.session import database_migration_versions


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

    assert data.data.missing_required_data >= 0
    assert data.data.unresolved_conflicts >= 0
    assert data.data.incomplete_assessments >= 0
    assert data.data.stale_source_data >= 0
    assert data.data.integration_failures >= 0
    assert data.data.pending_validation_facts >= 0
    assert data.data.pending_outbox_messages >= 0
    assert data.data.quarantined_evidence >= 0
    assert machine.data.diagnosis_confirm_total >= 0
    assert machine.data.diagnosis_modify_total >= 0
    assert machine.data.diagnosis_replace_total >= 0
    assert machine.data.schema_failures >= 0
    assert machine.data.ai_fallback_total >= 0
    assert machine.data.inference_failures >= 0
    assert machine.data.workflow_backlog >= 0
    assert machine.data.ai_decisions_total >= 0
    assert machine.data.learning_signal_raw >= 0
    assert machine.data.evaluation_pending >= 0
    assert machine.data.active_routing_policies >= 0

    migration_versions = await database_migration_versions()
    assert migration_versions
    assert all(migration_version for migration_version in migration_versions)

    await record_worker_heartbeat(
        worker_name="outbox-worker",
        settings=settings,
    )
    await record_worker_heartbeat(
        worker_name="temporal-worker",
        settings=settings,
    )
    snapshot = await read_operational_snapshot()
    assert snapshot.outbox_pending_count >= 0
    assert snapshot.outbox_oldest_age_seconds >= 0
    assert {heartbeat.worker_name for heartbeat in snapshot.heartbeats} >= {
        "outbox-worker",
        "temporal-worker",
    }

    await engine.dispose()
