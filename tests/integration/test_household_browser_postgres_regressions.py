"""Real PostgreSQL regression tests for browser-discovered case creation and OIDC races."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from hamoon.app.config.settings import get_settings
from hamoon.domains.household.application.commands import CreateHouseholdCommand
from hamoon.domains.household.application.handlers import CreateHouseholdHandler
from hamoon.domains.household.infrastructure.models import CaseAssignmentModel, HouseholdModel
from hamoon.domains.household.infrastructure.repositories import (
    SqlAlchemyCaseAssignmentRepository,
    SqlAlchemyHouseholdRepository,
)
from hamoon.domains.identity.domain.entities import ActorStatus, ActorType
from hamoon.domains.identity.infrastructure.models import ActorModel, UserAccountModel
from hamoon.domains.identity.infrastructure.repositories import SqlAlchemyIdentityRepository
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder


@pytest.mark.asyncio
async def test_household_creation_commits_parent_assignment_and_audit_atomically() -> None:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor_id = uuid4()
    now = datetime.now(UTC)
    case_code = f"QA-PG-{uuid4()}"

    try:
        async with sessions() as session:
            session.add(
                ActorModel(
                    id=actor_id,
                    actor_type=ActorType.HUMAN,
                    display_name="Synthetic integration caseworker",
                    status=ActorStatus.ACTIVE,
                    created_at=now,
                )
            )
            await session.commit()

        async with sessions() as session:
            async with session.begin():
                created = await CreateHouseholdHandler(
                    households=SqlAlchemyHouseholdRepository(session),
                    assignments=SqlAlchemyCaseAssignmentRepository(session),
                    events=SqlAlchemyDomainEventRecorder(session),
                    audits=SqlAlchemyAuditRecorder(session),
                ).handle(
                    CreateHouseholdCommand(
                        case_code=case_code,
                        actor_id=actor_id,
                        organizational_unit_id=None,
                        request_id="qa-pg-create",
                        correlation_id="qa-pg-create",
                    )
                )

        async with sessions() as session:
            parent = await session.get(HouseholdModel, created.id)
            assignment = (
                await session.execute(
                    select(CaseAssignmentModel).where(
                        CaseAssignmentModel.household_id == created.id
                    )
                )
            ).scalar_one()
            assert parent is not None
            assert parent.case_code == case_code
            assert parent.primary_caseworker_id == actor_id
            assert assignment.actor_id == actor_id
            assert assignment.assigned_by == actor_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_first_oidc_requests_provision_exactly_one_human_actor() -> None:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    issuer = "https://local-qa.example.invalid"
    subject = f"synthetic-browser-qa-{uuid4()}"
    now = datetime.now(UTC)

    async def resolve() -> str:
        async with sessions() as session:
            actor = await SqlAlchemyIdentityRepository(session).resolve_or_provision_human(
                issuer=issuer,
                subject=subject,
                display_name="Synthetic caseworker",
                now=now,
            )
            await session.commit()
            return str(actor.id)

    try:
        actor_ids = await asyncio.gather(*(resolve() for _ in range(6)))
        assert len(set(actor_ids)) == 1

        async with sessions() as session:
            accounts = (
                await session.execute(
                    select(UserAccountModel).where(
                        UserAccountModel.issuer == issuer,
                        UserAccountModel.external_identity_subject == subject,
                    )
                )
            ).scalars().all()
            assert len(accounts) == 1
            assert str(accounts[0].actor_id) == actor_ids[0]
            count = (
                await session.execute(
                    select(func.count()).select_from(ActorModel).where(
                        ActorModel.id == accounts[0].actor_id
                    )
                )
            ).scalar_one()
            assert count == 1
    finally:
        await engine.dispose()
