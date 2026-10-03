from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ActorType(StrEnum):
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"
    AI_ENGINE = "AI_ENGINE"
    PROVIDER = "PROVIDER"
    EXTERNAL_SYSTEM = "EXTERNAL_SYSTEM"


class ActorStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


@dataclass(frozen=True, slots=True)
class Actor:
    id: UUID
    actor_type: ActorType
    status: ActorStatus
    created_at: datetime
    display_name: str | None = None


@dataclass(frozen=True, slots=True)
class UserAccount:
    id: UUID
    actor_id: UUID
    issuer: str
    external_identity_subject: str
    created_at: datetime
    last_login_at: datetime | None = None
