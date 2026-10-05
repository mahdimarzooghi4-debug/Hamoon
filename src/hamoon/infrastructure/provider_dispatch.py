from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from hamoon.app.config.settings import Settings
from hamoon.domains.referral.domain.entities import ReferralDispatch


@dataclass(frozen=True, slots=True)
class ProviderDispatchTarget:
    endpoint: str
    bearer_token: str


class ProviderDispatchConfigurationError(RuntimeError):
    pass


class ProviderDispatchRetryableError(RuntimeError):
    pass


class ProviderDispatchPermanentError(RuntimeError):
    pass


def _remote_https(value: str) -> bool:
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or parsed.hostname is None:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    host = parsed.hostname.lower()
    return host != "localhost" and not host.endswith(".localhost")


def load_provider_dispatch_targets(
    settings: Settings,
) -> dict[UUID, ProviderDispatchTarget]:
    secret = settings.provider_dispatch_config
    if secret is None:
        raise ProviderDispatchConfigurationError(
            "PROVIDER_DISPATCH_CONFIG_REQUIRED"
        )
    raw = secret.get_secret_value().strip()
    if not raw:
        raise ProviderDispatchConfigurationError(
            "PROVIDER_DISPATCH_CONFIG_REQUIRED"
        )

    try:
        decoded_raw = cast(object, json.loads(raw))
    except json.JSONDecodeError as exc:
        raise ProviderDispatchConfigurationError(
            "PROVIDER_DISPATCH_CONFIG_INVALID"
        ) from exc
    if not isinstance(decoded_raw, dict) or not decoded_raw:
        raise ProviderDispatchConfigurationError(
            "PROVIDER_DISPATCH_CONFIG_INVALID"
        )
    decoded = cast(dict[str, object], decoded_raw)

    targets: dict[UUID, ProviderDispatchTarget] = {}
    for provider_id_text, value in decoded.items():
        try:
            provider_id = UUID(provider_id_text)
        except ValueError as exc:
            raise ProviderDispatchConfigurationError(
                "PROVIDER_DISPATCH_PROVIDER_ID_INVALID"
            ) from exc
        if not isinstance(value, dict):
            raise ProviderDispatchConfigurationError(
                "PROVIDER_DISPATCH_TARGET_INVALID"
            )
        target = cast(dict[str, object], value)
        endpoint = target.get("endpoint")
        bearer_token = target.get("bearer_token")
        if not isinstance(endpoint, str) or not _remote_https(endpoint):
            raise ProviderDispatchConfigurationError(
                "PROVIDER_DISPATCH_ENDPOINT_HTTPS_REQUIRED"
            )
        if not isinstance(bearer_token, str) or len(bearer_token.strip()) < 16:
            raise ProviderDispatchConfigurationError(
                "PROVIDER_DISPATCH_BEARER_TOKEN_INVALID"
            )
        targets[provider_id] = ProviderDispatchTarget(
            endpoint=endpoint.strip(),
            bearer_token=bearer_token.strip(),
        )
    return targets


class HttpProviderReferralDispatcher:
    def __init__(
        self,
        *,
        targets: dict[UUID, ProviderDispatchTarget],
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("PROVIDER_DISPATCH_TIMEOUT_INVALID")
        self._targets = targets
        self._timeout_seconds = timeout_seconds
        self._client = client

    async def _post(
        self,
        client: httpx.AsyncClient,
        dispatch: ReferralDispatch,
        target: ProviderDispatchTarget,
    ) -> httpx.Response:
        return await client.post(
            target.endpoint,
            json=dispatch.payload,
            headers={
                "Authorization": f"Bearer {target.bearer_token}",
                "Idempotency-Key": dispatch.idempotency_key,
                "X-Hamoon-Dispatch-Id": str(dispatch.id),
                "X-Hamoon-Referral-Id": str(dispatch.referral_id),
            },
        )

    async def send(self, dispatch: ReferralDispatch) -> None:
        target = self._targets.get(dispatch.provider_id)
        if target is None:
            raise ProviderDispatchConfigurationError(
                "PROVIDER_DISPATCH_TARGET_NOT_CONFIGURED"
            )

        try:
            if self._client is not None:
                response = await self._post(self._client, dispatch, target)
            else:
                async with httpx.AsyncClient(
                    timeout=self._timeout_seconds,
                    follow_redirects=False,
                ) as client:
                    response = await self._post(client, dispatch, target)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise ProviderDispatchRetryableError(
                "PROVIDER_DISPATCH_TRANSPORT_ERROR"
            ) from exc

        status = response.status_code
        if 200 <= status < 300:
            return
        if 500 <= status < 600:
            raise ProviderDispatchRetryableError(
                f"PROVIDER_DISPATCH_HTTP_{status}"
            )
        raise ProviderDispatchPermanentError(
            f"PROVIDER_DISPATCH_HTTP_{status}"
        )
