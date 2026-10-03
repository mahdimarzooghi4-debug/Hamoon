from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from hamoon.domains.identity.domain.entities import ActorType


class Role(StrEnum):
    CASEWORKER = "CASEWORKER"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"
    SECURITY_AUDITOR = "SECURITY_AUDITOR"


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    actor_id: UUID
    actor_type: ActorType
    subject: str
    issuer: str
    roles: frozenset[Role]
    scopes: frozenset[str]
    organization_id: str | None = None
    unit_id: str | None = None

    def has_role(self, role: Role) -> bool:
        return role in self.roles
