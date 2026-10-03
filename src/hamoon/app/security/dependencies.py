from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from hamoon.app.config.settings import get_settings
from hamoon.app.security.context import AuthorizationContext, Role
from hamoon.app.security.oidc import (
    AuthenticatedPrincipal,
    OIDCJWTValidator,
    TokenValidationError,
)
from hamoon.domains.identity.domain.entities import ActorStatus, ActorType
from hamoon.domains.identity.domain.errors import IdentityDisabledError
from hamoon.domains.identity.infrastructure.models import ActorModel
from hamoon.domains.identity.infrastructure.repositories import SqlAlchemyIdentityRepository
from hamoon.domains.provider.domain.entities import ProviderStatus
from hamoon.domains.provider.infrastructure.repositories import (
    SqlAlchemyProviderRegistryRepository,
)
from hamoon.infrastructure.db.session import session_factory

_bearer = HTTPBearer(auto_error=False)


@lru_cache
def get_oidc_validator() -> OIDCJWTValidator:
    return OIDCJWTValidator(get_settings())


async def _principal(
    credentials: HTTPAuthorizationCredentials | None,
    validator: OIDCJWTValidator,
) -> AuthenticatedPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED"},
        )
    try:
        return await validator.validate(credentials.credentials)
    except TokenValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED"},
        ) from exc


async def get_authorization_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    validator: Annotated[OIDCJWTValidator, Depends(get_oidc_validator)],
) -> AuthorizationContext:
    principal = await _principal(credentials, validator)
    machine_roles = {
        Role.PROVIDER_INTEGRATION,
        Role.SYSTEM_INTEGRATION,
        Role.AI_RUNTIME,
    }
    if principal.roles.intersection(machine_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "SERVICE_IDENTITY_REQUIRED"},
        )

    now = datetime.now(UTC)
    async with session_factory() as session:
        repository = SqlAlchemyIdentityRepository(session)
        try:
            actor = await repository.resolve_or_provision_human(
                issuer=principal.issuer,
                subject=principal.subject,
                display_name=principal.display_name,
                now=now,
            )
            await session.commit()
        except IdentityDisabledError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "IDENTITY_DISABLED"},
            ) from exc

    return AuthorizationContext(
        actor_id=actor.id,
        actor_type=actor.actor_type,
        subject=principal.subject,
        issuer=principal.issuer,
        roles=principal.roles,
        scopes=principal.scopes,
        organization_id=principal.organization_id,
        unit_id=principal.unit_id,
    )


async def get_provider_authorization_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    validator: Annotated[OIDCJWTValidator, Depends(get_oidc_validator)],
) -> AuthorizationContext:
    principal = await _principal(credentials, validator)
    if Role.PROVIDER_INTEGRATION not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN"},
        )

    async with session_factory() as session:
        registry = SqlAlchemyProviderRegistryRepository(session)
        identity = await registry.resolve_identity(
            issuer=principal.issuer,
            subject=principal.subject,
        )
        if identity is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "PROVIDER_IDENTITY_NOT_MAPPED"},
            )
        provider = await registry.get_provider(identity.provider_id)
        actor = await session.get(ActorModel, identity.actor_id)
        if (
            provider is None
            or provider.status is not ProviderStatus.ACTIVE
            or actor is None
            or actor.status is not ActorStatus.ACTIVE
            or actor.actor_type is not ActorType.PROVIDER
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "PROVIDER_IDENTITY_DISABLED"},
            )

    return AuthorizationContext(
        actor_id=identity.actor_id,
        actor_type=ActorType.PROVIDER,
        subject=principal.subject,
        issuer=principal.issuer,
        roles=frozenset({Role.PROVIDER_INTEGRATION}),
        scopes=principal.scopes,
        provider_id=identity.provider_id,
    )


def require_roles(*required_roles: Role):
    async def dependency(
        context: Annotated[AuthorizationContext, Depends(get_authorization_context)],
    ) -> AuthorizationContext:
        if not any(context.has_role(role) for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN"},
            )
        return context

    return dependency
