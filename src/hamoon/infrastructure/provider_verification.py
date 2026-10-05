from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

import httpx

from hamoon.infrastructure.provider_dispatch import ProviderDispatchTarget


class ProviderIntegrationVerificationError(RuntimeError):
    """Provider integration verification failed safely."""


def _require_string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderIntegrationVerificationError(f"{field} is required.")
    return value.strip()


def _validate_receipt(
    *,
    receipt: dict[str, object],
    provider_id: UUID,
    commit_sha: str,
    verification_id: str,
) -> dict[str, object]:
    if receipt.get("schema_version") != 1:
        raise ProviderIntegrationVerificationError(
            "Provider verification schema_version is unsupported."
        )
    if receipt.get("status") != "READY":
        raise ProviderIntegrationVerificationError(
            "Provider verification did not reach READY state."
        )
    if receipt.get("provider_id") != str(provider_id):
        raise ProviderIntegrationVerificationError(
            "Provider verification provider_id mismatch."
        )
    if receipt.get("commit_sha") != commit_sha:
        raise ProviderIntegrationVerificationError(
            "Provider verification commit_sha mismatch."
        )
    if receipt.get("verification_id") != verification_id:
        raise ProviderIntegrationVerificationError(
            "Provider verification verification_id mismatch."
        )

    checks = receipt.get("checks")
    if not isinstance(checks, dict):
        raise ProviderIntegrationVerificationError(
            "Provider verification checks are missing."
        )
    normalized_checks = cast(dict[str, object], checks)
    required_checks = (
        "credential_accepted",
        "dispatch_contract_supported",
        "idempotency_supported",
    )
    if set(normalized_checks) != set(required_checks):
        raise ProviderIntegrationVerificationError(
            "Provider verification check set is invalid."
        )
    failed = [
        check
        for check in required_checks
        if normalized_checks.get(check) is not True
    ]
    if failed:
        raise ProviderIntegrationVerificationError(
            "Provider verification failed required checks: "
            + ",".join(failed)
        )

    checked_at = _require_string(receipt.get("checked_at"), field="checked_at")
    try:
        timestamp = datetime.fromisoformat(checked_at)
    except ValueError as exc:
        raise ProviderIntegrationVerificationError(
            "Provider verification checked_at is invalid."
        ) from exc
    if timestamp.tzinfo is None:
        raise ProviderIntegrationVerificationError(
            "Provider verification checked_at must include timezone."
        )

    return dict(receipt)


async def verify_provider_integration(
    *,
    provider_id: UUID,
    target: ProviderDispatchTarget,
    commit_sha: str,
    timeout_seconds: float = 20.0,
    client: httpx.AsyncClient | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    if target.verification_endpoint is None:
        raise ProviderIntegrationVerificationError(
            "Provider verification endpoint is not configured."
        )
    if timeout_seconds <= 0:
        raise ProviderIntegrationVerificationError(
            "Provider verification timeout must be positive."
        )

    verification_id = f"hamoon-provider-verify-{uuid4()}"
    payload: dict[str, object] = {
        "schema_version": 1,
        "operation": "VERIFY_HAMOON_PROVIDER_INTEGRATION",
        "verification_id": verification_id,
        "provider_id": str(provider_id),
        "commit_sha": commit_sha,
        "synthetic": True,
        "contains_pii": False,
        "checks_requested": [
            "credential_accepted",
            "dispatch_contract_supported",
            "idempotency_supported",
        ],
    }
    headers = {
        "Authorization": f"Bearer {target.bearer_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Hamoon-Verification-Id": verification_id,
    }

    owns_client = client is None
    http_client = client or httpx.AsyncClient(
        timeout=timeout_seconds,
        follow_redirects=False,
    )
    try:
        response = await http_client.post(
            target.verification_endpoint,
            json=payload,
            headers=headers,
        )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise ProviderIntegrationVerificationError(
            "Provider verification transport failed."
        ) from exc
    finally:
        if owns_client:
            await http_client.aclose()

    if response.status_code < 200 or response.status_code >= 300:
        raise ProviderIntegrationVerificationError(
            f"Provider verification returned HTTP {response.status_code}."
        )
    try:
        raw = cast(object, response.json())
    except ValueError as exc:
        raise ProviderIntegrationVerificationError(
            "Provider verification returned invalid JSON."
        ) from exc
    if not isinstance(raw, dict):
        raise ProviderIntegrationVerificationError(
            "Provider verification response must be a JSON object."
        )
    receipt = _validate_receipt(
        receipt=cast(dict[str, object], raw),
        provider_id=provider_id,
        commit_sha=commit_sha,
        verification_id=verification_id,
    )
    return payload, receipt
