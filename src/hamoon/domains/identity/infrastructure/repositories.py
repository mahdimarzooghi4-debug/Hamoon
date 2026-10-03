from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.identity.domain.entities import Actor, ActorStatus, ActorType
from hamoon.domains.identity.domain.errors import IdentityDisabledError
from hamoon.domains.identity.infrastructure.models import ActorModel, UserAccountModel


class SqlAlchemyIdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_or_provision_human(
        self,
        *,
        issuer: str,
        subject: str,
        display_name: str | None,
        now: datetime,
    ) -> Actor:
        result = await self._session.execute(
            select(UserAccountModel, ActorModel)
            .join(ActorModel, ActorModel.id == UserAccountModel.actor_id)
            .where(
                UserAccountModel.issuer == issuer,
                UserAccountModel.external_identity_subject == subject,
            )
        )
        row = result.one_or_none()

        if row is not None:
            _account, actor = row
            if actor.status is ActorStatus.DISABLED:
                raise IdentityDisabledError("Identity is disabled.")

            if display_name and actor.display_name != display_name:
                actor.display_name = display_name

            return Actor(
                id=actor.id,
                actor_type=actor.actor_type,
                status=actor.status,
                created_at=actor.created_at,
                display_name=actor.display_name,
            )

        actor_id = uuid4()
        actor_model = ActorModel(
            id=actor_id,
            actor_type=ActorType.HUMAN,
            display_name=display_name,
            status=ActorStatus.ACTIVE,
            created_at=now,
        )
        account_model = UserAccountModel(
            id=uuid4(),
            actor_id=actor_id,
            issuer=issuer,
            external_identity_subject=subject,
            last_login_at=now,
            created_at=now,
        )
        self._session.add_all([actor_model, account_model])

        return Actor(
            id=actor_id,
            actor_type=ActorType.HUMAN,
            status=ActorStatus.ACTIVE,
            created_at=now,
            display_name=display_name,
        )
