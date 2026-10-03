from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.domains.identity.domain.entities import ActorStatus, ActorType
from hamoon.infrastructure.db.base import Base


class ActorModel(Base):
    __tablename__ = "actor"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, name="actor_type"),
        nullable=False,
    )
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[ActorStatus] = mapped_column(
        Enum(ActorStatus, name="actor_status"),
        nullable=False,
        default=ActorStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserAccountModel(Base):
    __tablename__ = "user_account"
    __table_args__ = (
        UniqueConstraint(
            "issuer",
            "external_identity_subject",
            name="uq_user_account_issuer_subject",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    issuer: Mapped[str] = mapped_column(String(500), nullable=False)
    external_identity_subject: Mapped[str] = mapped_column(String(500), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
