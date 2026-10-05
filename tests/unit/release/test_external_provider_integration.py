from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

COMMIT = "a" * 40
PROVIDER_ID = "11111111-1111-1111-1111-111111111111"


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _chain(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    stage = tmp_path / "stage-attestation.json"
    _write_json(
        stage,
        {
            "schema_version": 1,
            "status": "PASSED",
            "commit_sha": COMMIT,
            "stage_admission_run_id": "202",
        },
    )

    request = tmp_path / "provider-verification-request.json"
    _write_json(
        request,
        {
            "schema_version": 1,
            "operation": "VERIFY_HAMOON_PROVIDER_INTEGRATION",
            "verification_id": "hamoon-provider-verify-test",
            "provider_id": PROVIDER_ID,
            "commit_sha": COMMIT,
            "synthetic": True,
            "contains_pii": False,
            "checks_requested": [
                "credential_accepted",
                "dispatch_contract_supported",
                "idempotency_supported",
            ],
        },
    )

    receipt = tmp_path / "provider-verification-receipt.json"
    _write_json(
        receipt,
        {
            "schema_version": 1,
            "status": "READY",
            "verification_id": "hamoon-provider-verify-test",
            "provider_id": PROVIDER_ID,
            "commit_sha": COMMIT,
            "checks": {
                "credential_accepted": True,
                "dispatch_contract_supported": True,
                "idempotency_supported": True,
            },
            "checked_at": "2026-10-05T13:00:00+00:00",
        },
    )

    attestation = tmp_path / "provider-integration-verification.json"
    _write_json(
        attestation,
        {
            "schema_version": 1,
            "status": "VERIFIED",
            "verification_scope": "EXTERNAL_PROVIDER_INTEGRATION",
            "external_provider_integration_verified": True,
            "commit_sha": COMMIT,
            "provider_id": PROVIDER_ID,
            "verification_id": "hamoon-provider-verify-test",
            "stage_admission_run_id": "202",
            "provider_verification_run_id": "303",
            "stage_attestation_sha256": hashlib.sha256(
                stage.read_bytes()
            ).hexdigest(),
            "provider_verification_request_sha256": hashlib.sha256(
                request.read_bytes()
            ).hexdigest(),
            "provider_verification_receipt_sha256": hashlib.sha256(
                receipt.read_bytes()
            ).hexdigest(),
            "verifier": "production-operator",
            "verified_at": "2026-10-05T13:01:00+00:00",
        },
    )
    return stage, request, receipt, attestation


def _verify(
    stage: Path,
    request: Path,
    receipt: Path,
    attestation: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/verify_external_provider_integration.py",
            str(stage),
            str(request),
            str(receipt),
            str(attestation),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_external_provider_verifier_accepts_bound_synthetic_evidence(
    tmp_path: Path,
) -> None:
    result = _verify(*_chain(tmp_path))

    assert result.returncode == 0
    assert '"status": "valid"' in result.stdout


def test_external_provider_verifier_rejects_tampered_receipt(
    tmp_path: Path,
) -> None:
    stage, request, receipt, attestation = _chain(tmp_path)
    receipt.write_text(receipt.read_text() + " ", encoding="utf-8")

    result = _verify(stage, request, receipt, attestation)

    assert result.returncode != 0
    assert "provider_verification_receipt_sha256 mismatch" in result.stderr


def test_external_provider_verifier_rejects_pii_claim(
    tmp_path: Path,
) -> None:
    stage, request, receipt, attestation = _chain(tmp_path)
    value = json.loads(request.read_text())
    value["contains_pii"] = True
    _write_json(request, value)
    attestation_value = json.loads(attestation.read_text())
    attestation_value["provider_verification_request_sha256"] = hashlib.sha256(
        request.read_bytes()
    ).hexdigest()
    _write_json(attestation, attestation_value)

    result = _verify(stage, request, receipt, attestation)

    assert result.returncode != 0
    assert "request must declare no PII" in result.stderr


def test_external_provider_verifier_rejects_forbidden_evidence_fields(
    tmp_path: Path,
) -> None:
    stage, request, receipt, attestation = _chain(tmp_path)
    value = json.loads(receipt.read_text())
    value["referral_id"] = "should-not-exist"
    _write_json(receipt, value)
    attestation_value = json.loads(attestation.read_text())
    attestation_value["provider_verification_receipt_sha256"] = hashlib.sha256(
        receipt.read_bytes()
    ).hexdigest()
    _write_json(attestation, attestation_value)

    result = _verify(stage, request, receipt, attestation)

    assert result.returncode != 0
    assert "forbidden evidence fields present" in result.stderr
