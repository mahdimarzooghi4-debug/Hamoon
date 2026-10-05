from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from hamoon.app.config.settings import Settings
from hamoon.domains.referral.domain.entities import ReferralDispatch
from hamoon.infrastructure.provider_dispatch import (
    HttpProviderReferralDispatcher,
    ProviderDispatchConfigurationError,
    ProviderDispatchPermanentError,
    ProviderDispatchRetryableError,
    load_provider_dispatch_targets,
)

PROVIDER_ID = UUID("11111111-1111-1111-1111-111111111111")
REFERRAL_ID = UUID("22222222-2222-2222-2222-222222222222")
DISPATCH_ID = UUID("33333333-3333-3333-3333-333333333333")


def _settings(*, endpoint: str = "https://provider.example/referrals") -> Settings:
    return Settings(
        _env_file=None,
        provider_dispatch_config=json.dumps(
            {
                str(PROVIDER_ID): {
                    "endpoint": endpoint,
                    "bearer_token": "provider-secret-token-123456",
                }
            }
        ),
    )


def _dispatch() -> ReferralDispatch:
    return ReferralDispatch(
        id=DISPATCH_ID,
        referral_id=REFERRAL_ID,
        provider_id=PROVIDER_ID,
        idempotency_key="dispatch-idempotency-1",
        request_hash="a" * 64,
        payload={
            "schema_version": "provider-referral-v1",
            "callback_reference": "href_123",
            "authorized_data": {"geo.coverage_code": ["TEHRAN-1"]},
        },
        status="PENDING",
        created_at=datetime.now(UTC),
        sent_at=None,
    )


def test_provider_dispatch_config_requires_remote_https() -> None:
    with pytest.raises(
        ProviderDispatchConfigurationError,
        match="PROVIDER_DISPATCH_ENDPOINT_HTTPS_REQUIRED",
    ):
        load_provider_dispatch_targets(
            _settings(endpoint="http://localhost:9009/referrals")
        )


@pytest.mark.asyncio
async def test_provider_dispatch_sends_minimized_payload_with_idempotency() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(202, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    ) as client:
        dispatcher = HttpProviderReferralDispatcher(
            targets=load_provider_dispatch_targets(_settings()),
            timeout_seconds=5,
            client=client,
        )
        await dispatcher.send(_dispatch())

    assert len(requests) == 1
    request = requests[0]
    assert request.headers["Idempotency-Key"] == "dispatch-idempotency-1"
    assert request.headers["X-Hamoon-Dispatch-Id"] == str(DISPATCH_ID)
    assert request.headers["X-Hamoon-Referral-Id"] == str(REFERRAL_ID)
    assert request.headers["Authorization"] == "Bearer provider-secret-token-123456"
    assert json.loads(request.content) == _dispatch().payload


@pytest.mark.asyncio
async def test_provider_dispatch_treats_5xx_as_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as client:
        dispatcher = HttpProviderReferralDispatcher(
            targets=load_provider_dispatch_targets(_settings()),
            timeout_seconds=5,
            client=client,
        )
        with pytest.raises(
            ProviderDispatchRetryableError,
            match="PROVIDER_DISPATCH_HTTP_503",
        ):
            await dispatcher.send(_dispatch())


@pytest.mark.asyncio
async def test_provider_dispatch_treats_4xx_as_permanent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as client:
        dispatcher = HttpProviderReferralDispatcher(
            targets=load_provider_dispatch_targets(_settings()),
            timeout_seconds=5,
            client=client,
        )
        with pytest.raises(
            ProviderDispatchPermanentError,
            match="PROVIDER_DISPATCH_HTTP_422",
        ):
            await dispatcher.send(_dispatch())
