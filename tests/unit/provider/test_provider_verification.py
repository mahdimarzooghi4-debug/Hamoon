from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from hamoon.infrastructure.provider_dispatch import ProviderDispatchTarget
from hamoon.infrastructure.provider_verification import (
    ProviderIntegrationVerificationError,
    verify_provider_integration,
)

PROVIDER_ID = UUID("11111111-1111-1111-1111-111111111111")
COMMIT = "a" * 40
TOKEN = "provider-verification-token-123456"


def _target() -> ProviderDispatchTarget:
    return ProviderDispatchTarget(
        endpoint="https://provider.example/referrals",
        verification_endpoint="https://provider.example/integration/verify",
        bearer_token=TOKEN,
    )


def _receipt(verification_id: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "READY",
        "provider_id": str(PROVIDER_ID),
        "commit_sha": COMMIT,
        "verification_id": verification_id,
        "checks": {
            "credential_accepted": True,
            "dispatch_contract_supported": True,
            "idempotency_supported": True,
        },
        "checked_at": datetime.now(UTC).isoformat(),
    }


@pytest.mark.asyncio
async def test_provider_verification_sends_synthetic_non_pii_probe() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        captured["authorization"] = request.headers["Authorization"]
        captured["verification_id"] = request.headers["X-Hamoon-Verification-Id"]
        captured["payload"] = payload
        return httpx.Response(
            200,
            json=_receipt(payload["verification_id"]),
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    ) as client:
        request_payload, receipt = await verify_provider_integration(
            provider_id=PROVIDER_ID,
            target=_target(),
            commit_sha=COMMIT,
            client=client,
        )

    assert captured["authorization"] == f"Bearer {TOKEN}"
    assert captured["verification_id"] == request_payload["verification_id"]
    assert request_payload["operation"] == "VERIFY_HAMOON_PROVIDER_INTEGRATION"
    assert request_payload["synthetic"] is True
    assert request_payload["contains_pii"] is False
    assert "referral_id" not in request_payload
    assert "household_id" not in request_payload
    assert receipt["status"] == "READY"


@pytest.mark.asyncio
async def test_provider_verification_requires_configured_verification_endpoint() -> None:
    with pytest.raises(
        ProviderIntegrationVerificationError,
        match="verification endpoint is not configured",
    ):
        await verify_provider_integration(
            provider_id=PROVIDER_ID,
            target=ProviderDispatchTarget(
                endpoint="https://provider.example/referrals",
                bearer_token=TOKEN,
            ),
            commit_sha=COMMIT,
        )


@pytest.mark.asyncio
async def test_provider_verification_rejects_false_required_check() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        receipt = _receipt(payload["verification_id"])
        checks = receipt["checks"]
        assert isinstance(checks, dict)
        checks["idempotency_supported"] = False
        return httpx.Response(200, json=receipt, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    ) as client:
        with pytest.raises(
            ProviderIntegrationVerificationError,
            match="failed required checks: idempotency_supported",
        ):
            await verify_provider_integration(
                provider_id=PROVIDER_ID,
                target=_target(),
                commit_sha=COMMIT,
                client=client,
            )


@pytest.mark.asyncio
async def test_provider_verification_rejects_receipt_identity_drift() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        receipt = _receipt(payload["verification_id"])
        receipt["provider_id"] = str(
            UUID("22222222-2222-2222-2222-222222222222")
        )
        return httpx.Response(200, json=receipt, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    ) as client:
        with pytest.raises(
            ProviderIntegrationVerificationError,
            match="provider_id mismatch",
        ):
            await verify_provider_integration(
                provider_id=PROVIDER_ID,
                target=_target(),
                commit_sha=COMMIT,
                client=client,
            )
