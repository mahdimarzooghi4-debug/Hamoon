#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_KEYS = {
    "authorization",
    "bearer_token",
    "token",
    "household_id",
    "referral_id",
    "dispatch_id",
    "national_id",
    "phone",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"provider integration verification invalid: {message}")


def load_json(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"provider integration verification invalid: cannot parse {path}"
        ) from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recursive_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key).lower())
            keys.update(recursive_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(recursive_keys(item))
    return keys


def timestamp(value: object, field: str) -> datetime:
    require(isinstance(value, str), f"{field} missing")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(
            f"provider integration verification invalid: {field} invalid"
        ) from exc
    require(parsed.tzinfo is not None, f"{field} must include timezone")
    return parsed


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit(
            "usage: verify_external_provider_integration.py "
            "<stage-attestation.json> <request.json> <receipt.json> <attestation.json>"
        )

    stage_path = Path(sys.argv[1])
    request_path = Path(sys.argv[2])
    receipt_path = Path(sys.argv[3])
    attestation_path = Path(sys.argv[4])

    stage = load_json(stage_path)
    request = load_json(request_path)
    receipt = load_json(receipt_path)
    attestation = load_json(attestation_path)

    require(stage.get("status") == "PASSED", "Stage Admission is not PASSED")
    commit_sha = stage.get("commit_sha")
    require(
        isinstance(commit_sha, str) and COMMIT_RE.fullmatch(commit_sha) is not None,
        "Stage commit_sha invalid",
    )
    stage_run_id = stage.get("stage_admission_run_id")
    require(
        isinstance(stage_run_id, str) and stage_run_id.isdigit(),
        "stage_admission_run_id invalid",
    )

    require(
        request.get("schema_version") == 1,
        "request schema_version unsupported",
    )
    require(
        request.get("operation") == "VERIFY_HAMOON_PROVIDER_INTEGRATION",
        "request operation invalid",
    )
    require(request.get("commit_sha") == commit_sha, "request commit mismatch")
    require(request.get("synthetic") is True, "request must be synthetic")
    require(request.get("contains_pii") is False, "request must declare no PII")
    provider_id = request.get("provider_id")
    require(
        isinstance(provider_id, str) and bool(provider_id),
        "request provider_id missing",
    )
    verification_id = request.get("verification_id")
    require(
        isinstance(verification_id, str) and verification_id.startswith(
            "hamoon-provider-verify-"
        ),
        "request verification_id invalid",
    )
    required_checks = [
        "credential_accepted",
        "dispatch_contract_supported",
        "idempotency_supported",
    ]
    require(
        request.get("checks_requested") == required_checks,
        "request check set invalid",
    )

    require(receipt.get("schema_version") == 1, "receipt schema_version unsupported")
    require(receipt.get("status") == "READY", "receipt status must be READY")
    require(receipt.get("provider_id") == provider_id, "receipt provider_id mismatch")
    require(receipt.get("commit_sha") == commit_sha, "receipt commit mismatch")
    require(
        receipt.get("verification_id") == verification_id,
        "receipt verification_id mismatch",
    )
    checks = receipt.get("checks")
    require(isinstance(checks, dict), "receipt checks missing")
    require(set(checks) == set(required_checks), "receipt check set invalid")
    for check in required_checks:
        require(checks.get(check) is True, f"receipt required check failed: {check}")
    checked_at = timestamp(receipt.get("checked_at"), "receipt checked_at")

    leaked = FORBIDDEN_KEYS & (recursive_keys(request) | recursive_keys(receipt))
    require(not leaked, f"forbidden evidence fields present {sorted(leaked)}")

    require(attestation.get("schema_version") == 1, "attestation schema unsupported")
    require(attestation.get("status") == "VERIFIED", "attestation status invalid")
    require(
        attestation.get("verification_scope") == "EXTERNAL_PROVIDER_INTEGRATION",
        "attestation verification_scope invalid",
    )
    require(
        attestation.get("external_provider_integration_verified") is True,
        "external provider integration not verified",
    )
    require(attestation.get("commit_sha") == commit_sha, "attestation commit mismatch")
    require(attestation.get("provider_id") == provider_id, "attestation provider mismatch")
    require(
        attestation.get("verification_id") == verification_id,
        "attestation verification_id mismatch",
    )
    require(
        attestation.get("stage_admission_run_id") == stage_run_id,
        "attestation Stage run mismatch",
    )

    verification_run_id = attestation.get("provider_verification_run_id")
    require(
        isinstance(verification_run_id, str) and verification_run_id.isdigit(),
        "provider_verification_run_id invalid",
    )
    verifier = attestation.get("verifier")
    require(
        isinstance(verifier, str) and verifier and not verifier.endswith("[bot]"),
        "verifier must be a human GitHub actor",
    )
    verified_at = timestamp(attestation.get("verified_at"), "verified_at")
    require(verified_at >= checked_at, "verified_at precedes provider receipt")

    for field, path in (
        ("stage_attestation_sha256", stage_path),
        ("provider_verification_request_sha256", request_path),
        ("provider_verification_receipt_sha256", receipt_path),
    ):
        value = attestation.get(field)
        require(
            isinstance(value, str) and SHA256_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )
        require(value == digest(path), f"{field} mismatch")

    print(
        json.dumps(
            {
                "status": "valid",
                "commit_sha": commit_sha,
                "provider_id": provider_id,
                "verification_id": verification_id,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
