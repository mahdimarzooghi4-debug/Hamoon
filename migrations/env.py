from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from hamoon.app.config.settings import get_settings
from hamoon.infrastructure.db.base import Base

from hamoon.domains.assessment.infrastructure import models as assessment_models  # noqa: F401
from hamoon.domains.family_data.infrastructure import models as family_data_models  # noqa: F401
from hamoon.domains.household.infrastructure import models as household_models  # noqa: F401
from hamoon.domains.identity.infrastructure import models as identity_models  # noqa: F401
from hamoon.domains.intelligence.infrastructure import models as intelligence_models  # noqa: F401
from hamoon.domains.intervention.infrastructure import models as intervention_models  # noqa: F401
from hamoon.domains.pgor.infrastructure import models as pgor_models  # noqa: F401
from hamoon.domains.prescription.infrastructure import models as prescription_models  # noqa: F401
from hamoon.domains.provider.infrastructure import models as provider_models  # noqa: F401
from hamoon.domains.referral.infrastructure import models as referral_models  # noqa: F401
from hamoon.infrastructure.audit import models as audit_models  # noqa: F401
from hamoon.infrastructure.events import models as event_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio

    asyncio.run(run_migrations_online())
