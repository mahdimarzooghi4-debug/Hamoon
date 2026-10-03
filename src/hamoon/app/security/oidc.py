from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import cast

import httpx
import jwt

from hamoon.app.config.settings import Settings
from hamoon.app.security.context import Role


class TokenValidationError(ValueError):
    """Raised when an OIDC access token cannot be trusted."""


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    subject: str
    issuer: str
    roles: frozenset[Role]
    scopes: frozenset[str]
    display_name: str | None
    organization_id: str | None
    unit_id: str | None


def _as_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _extract_roles(claims: dict[str, object]) -> frozenset[Role]:
    names: set[str] = set()

    direct_roles = claims.get("roles")
    if isinstance(direct_roles, list):
        names.update(
            item
            for item in cast(list[object], direct_roles)
            if isinstance(item, str)
        )

    realm_access = claims.get("realm_access")
    if isinstance(realm_access, dict):
        realm_access_object = cast(dict[str, object], realm_access)
        realm_roles = realm_access_object.get("roles")
        if isinstance(realm_roles, list):
            names.update(
                item
                for item in cast(list[object], realm_roles)
                if isinstance(item, str)
            )

    return frozenset(role for role in Role if role.value in names)


def principal_from_claims(claims: dict[str, object]) -> AuthenticatedPrincipal:
    subject = _as_string(claims.get("sub"))
    issuer = _as_string(claims.get("iss"))

    if subject is None or issuer is None:
        raise TokenValidationError("Required OIDC subject/issuer claim is missing.")

    scope_claim = claims.get("scope")
    scopes: frozenset[str] = (
        frozenset(scope_claim.split())
        if isinstance(scope_claim, str)
        else frozenset()
    )

    display_name = _as_string(claims.get("name")) or _as_string(
        claims.get("preferred_username")
    )

    return AuthenticatedPrincipal(
        subject=subject,
        issuer=issuer,
        roles=_extract_roles(claims),
        scopes=scopes,
        display_name=display_name,
        organization_id=_as_string(claims.get("organization_id")),
        unit_id=_as_string(claims.get("unit_id")),
    )


class OIDCJWTValidator:
    """Validates signed OIDC JWT access tokens against issuer JWKS."""

    def __init__(
        self,
        settings: Settings,
        *,
        cache_ttl_seconds: float = 300.0,
    ) -> None:
        self._issuer = settings.oidc_issuer_url.rstrip("/")
        self._audience = settings.oidc_audience
        self._configured_jwks_url = (
            settings.oidc_jwks_url.rstrip("/")
            if settings.oidc_jwks_url
            else None
        )
        self._clock_skew = settings.oidc_clock_skew_seconds
        self._cache_ttl_seconds = cache_ttl_seconds
        self._jwks_uri: str | None = self._configured_jwks_url
        self._jwks: dict[str, object] | None = None
        self._jwks_cached_at = 0.0
        self._lock = asyncio.Lock()

    async def validate(self, token: str) -> AuthenticatedPrincipal:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenValidationError("Invalid JWT header.") from exc

        algorithm = header.get("alg")
        kid = header.get("kid")

        if algorithm != "RS256" or not isinstance(kid, str):
            raise TokenValidationError("Unsupported JWT signing algorithm or key id.")

        key_data = await self._find_key(kid)
        if key_data is None:
            await self._refresh_jwks(force=True)
            key_data = await self._find_key(kid)

        if key_data is None:
            raise TokenValidationError("JWT signing key was not found.")

        try:
            signing_key = jwt.PyJWK.from_dict(key_data, algorithm="RS256").key
            decoded = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._clock_skew,
                options={"require": ["exp", "iss", "sub", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise TokenValidationError("OIDC access token validation failed.") from exc

        claims = cast(dict[str, object], decoded)
        return principal_from_claims(claims)

    async def _find_key(self, kid: str) -> dict[str, object] | None:
        await self._refresh_jwks()
        assert self._jwks is not None

        raw_keys = self._jwks.get("keys")
        if not isinstance(raw_keys, list):
            return None

        for item in cast(list[object], raw_keys):
            if not isinstance(item, dict):
                continue
            key_object = cast(dict[str, object], item)
            if key_object.get("kid") == kid:
                return key_object
        return None

    async def _refresh_jwks(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if (
            not force
            and self._jwks is not None
            and now - self._jwks_cached_at < self._cache_ttl_seconds
        ):
            return

        async with self._lock:
            now = time.monotonic()
            if (
                not force
                and self._jwks is not None
                and now - self._jwks_cached_at < self._cache_ttl_seconds
            ):
                return

            jwks_uri = await self._resolve_jwks_uri()

            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(jwks_uri)
                    response.raise_for_status()
                    raw_data = cast(object, response.json())
            except (httpx.HTTPError, ValueError) as exc:
                raise TokenValidationError("OIDC JWKS could not be loaded.") from exc

            if not isinstance(raw_data, dict):
                raise TokenValidationError("OIDC JWKS response is invalid.")
            data = cast(dict[str, object], raw_data)
            if not isinstance(data.get("keys"), list):
                raise TokenValidationError("OIDC JWKS response is invalid.")

            self._jwks = data
            self._jwks_cached_at = time.monotonic()

    async def _resolve_jwks_uri(self) -> str:
        if self._jwks_uri is not None:
            return self._jwks_uri

        discovery_url = f"{self._issuer}/.well-known/openid-configuration"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(discovery_url)
                response.raise_for_status()
                raw_data = cast(object, response.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise TokenValidationError("OIDC discovery could not be loaded.") from exc

        if not isinstance(raw_data, dict):
            raise TokenValidationError("OIDC discovery response is invalid.")
        data = cast(dict[str, object], raw_data)

        jwks_uri = data.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise TokenValidationError("OIDC discovery did not provide jwks_uri.")

        self._jwks_uri = jwks_uri
        return jwks_uri
