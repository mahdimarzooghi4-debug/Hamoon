from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

COMMIT = "a" * 40
API_IMAGE_ID = "sha256:" + "b" * 64
WEB_IMAGE_ID = "sha256:" + "c" * 64
DEPLOYMENT_ID = "prod-20261005-001"
CHECKS = [
    "postgresql_connectivity",
    "nats_jetstream_connectivity",
    "temporal_connectivity",
    "oidc_discovery_https",
    "evidence_s3_private_https",
    "evidence_scanner_https",
    "otlp_traces_https",
    "otlp_logs_https",
    "protected_metrics_configured",
    "gemma4_checkpoint_attested",
    "provider_dispatch_configured",
    "backup_policy_configured",
    "retention_policy_configured",
]

CHECKPOINT = {
    "model_id": "google/gemma-4-12B-it",
    "revision": "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7",
    "model_sha256": "5a84cb313260ac447237b890387116dfa8682e49a6b44bc585ae8353abbff18d",
    "tokenizer_sha256": "cc8d3a0ce36466ccc1278bf987df5f71db1719b9ca6b4118264f45cb627bfe0f",
    "execution_mode": "IN_PROCESS",
    "network_model_download": False,
}


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _chain(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, Path, Path, Path, Path]:
    release = tmp_path / "release"
    release.mkdir()
    manifest = release / "manifest.json"
    _write_json(
        manifest,
        {
            "schema_version": 2,
            "commit_sha": COMMIT,
            "workflow_run_id": "101",
            "backend": {
                "image_id": API_IMAGE_ID,
                "archive": "hamoon-api.tar",
                "archive_sha256": "d" * 64,
            },
            "frontend": {
                "image_id": WEB_IMAGE_ID,
                "archive": "hamoon-web.tar",
                "archive_sha256": "e" * 64,
            },
        },
    )
    manifest_sha256 = hashlib.sha256(manifest.read_bytes()).hexdigest()

    admission = tmp_path / "production-deployment-admission.json"
    _write_json(
        admission,
        {
            "schema_version": 1,
            "status": "ADMITTED",
            "production_deployed": False,
            "commit_sha": COMMIT,
            "source_ci_run_id": "101",
            "stage_admission_run_id": "202",
            "release_approval_run_id": "303",
            "deployment_admission_run_id": "404",
            "production_target": "hamoon-prod-primary",
            "production_endpoint": "https://hamoon.example.com",
            "expected_deployment_id": DEPLOYMENT_ID,
            "backend_image_id": API_IMAGE_ID,
            "frontend_image_id": WEB_IMAGE_ID,
            "release_manifest_sha256": manifest_sha256,
            "release_approval_sha256": "f" * 64,
        },
    )

    requirements = tmp_path / "runtime-preflight.json"
    _write_json(
        requirements,
        {
            "schema_version": 2,
            "contract": "HAMOON_PRODUCTION_RUNTIME_PREFLIGHT",
            "required_checks": CHECKS,
            "internal_model_checkpoint": CHECKPOINT,
        },
    )
    requirements_sha256 = hashlib.sha256(requirements.read_bytes()).hexdigest()

    shared = {
        "schema_version": 1,
        "repository": "owner/Hamoon",
        "release_artifact_name": f"hamoon-release-{COMMIT}",
        "commit_sha": COMMIT,
        "source_ci_run_id": "101",
        "production_target": "hamoon-prod-primary",
        "production_endpoint": "https://hamoon.example.com",
        "deployment_id": DEPLOYMENT_ID,
        "backend": {
            "image_id": API_IMAGE_ID,
            "archive": "hamoon-api.tar",
            "archive_sha256": "d" * 64,
        },
        "frontend": {
            "image_id": WEB_IMAGE_ID,
            "archive": "hamoon-web.tar",
            "archive_sha256": "e" * 64,
        },
        "governance": {
            "release_approval_run_id": "303",
            "deployment_admission_run_id": "404",
            "release_manifest_sha256": manifest_sha256,
            "release_approval_sha256": "f" * 64,
        },
    }

    preflight_request = tmp_path / "preflight-request.json"
    _write_json(
        preflight_request,
        {
            **shared,
            "operation": "PREFLIGHT_HAMOON_PRODUCTION",
            "runtime_preflight": {
                "contract_sha256": requirements_sha256,
                "required_checks": CHECKS,
                "internal_model_checkpoint": CHECKPOINT,
            },
        },
    )

    preflight_receipt = tmp_path / "preflight-receipt.json"
    _write_json(
        preflight_receipt,
        {
            "status": "READY",
            "preflight_id": "preflight-001",
            "commit_sha": COMMIT,
            "deployment_id": DEPLOYMENT_ID,
            "production_target": "hamoon-prod-primary",
            "production_endpoint": "https://hamoon.example.com",
            "backend_image_id": API_IMAGE_ID,
            "frontend_image_id": WEB_IMAGE_ID,
            "checks": {check: True for check in CHECKS},
            "internal_model_checkpoint": CHECKPOINT,
            "checked_at": "2026-10-05T12:55:00+00:00",
        },
    )

    request = tmp_path / "orchestrator-request.json"
    _write_json(
        request,
        {
            **shared,
            "operation": "DEPLOY_HAMOON_RELEASE",
            "runtime_preflight": {
                "preflight_id": "preflight-001",
                "contract_sha256": requirements_sha256,
            },
        },
    )

    receipt = tmp_path / "orchestrator-receipt.json"
    _write_json(
        receipt,
        {
            "status": "DEPLOYED",
            "receipt_id": "receipt-001",
            "commit_sha": COMMIT,
            "deployment_id": DEPLOYMENT_ID,
            "production_target": "hamoon-prod-primary",
            "production_endpoint": "https://hamoon.example.com",
            "backend_image_id": API_IMAGE_ID,
            "frontend_image_id": WEB_IMAGE_ID,
            "preflight_id": "preflight-001",
            "deployed_at": "2026-10-05T13:00:00+00:00",
        },
    )

    deployment = tmp_path / "production-deployment.json"
    _write_json(
        deployment,
        {
            "schema_version": 1,
            "status": "DEPLOYED",
            "deployment_scope": "HOSTED_PRODUCTION_EXECUTION",
            "production_deployed": True,
            "commit_sha": COMMIT,
            "source_ci_run_id": "101",
            "stage_admission_run_id": "202",
            "release_approval_run_id": "303",
            "deployment_admission_run_id": "404",
            "production_deployment_run_id": "505",
            "production_target": "hamoon-prod-primary",
            "production_endpoint": "https://hamoon.example.com",
            "deployment_id": DEPLOYMENT_ID,
            "backend_image_id": API_IMAGE_ID,
            "frontend_image_id": WEB_IMAGE_ID,
            "preflight_id": "preflight-001",
            "receipt_id": "receipt-001",
            "runtime_preflight_contract_sha256": requirements_sha256,
            "preflight_request_sha256": hashlib.sha256(
                preflight_request.read_bytes()
            ).hexdigest(),
            "preflight_receipt_sha256": hashlib.sha256(
                preflight_receipt.read_bytes()
            ).hexdigest(),
            "release_manifest_sha256": manifest_sha256,
            "deployment_admission_sha256": hashlib.sha256(
                admission.read_bytes()
            ).hexdigest(),
            "orchestrator_request_sha256": hashlib.sha256(
                request.read_bytes()
            ).hexdigest(),
            "orchestrator_receipt_sha256": hashlib.sha256(
                receipt.read_bytes()
            ).hexdigest(),
            "deployer": "production-operator",
            "triggering_actor": "production-operator",
            "deployed_at": "2026-10-05T13:00:00+00:00",
            "attested_at": "2026-10-05T13:01:00+00:00",
        },
    )

    return (
        release,
        admission,
        requirements,
        preflight_request,
        preflight_receipt,
        request,
        receipt,
        deployment,
    )


def _verify(
    release: Path,
    admission: Path,
    requirements: Path,
    preflight_request: Path,
    preflight_receipt: Path,
    request: Path,
    receipt: Path,
    deployment: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/verify_production_deployment.py",
            str(release),
            str(admission),
            str(requirements),
            str(preflight_request),
            str(preflight_receipt),
            str(request),
            str(receipt),
            str(deployment),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_production_deployment_verifier_accepts_bound_preflight_and_receipt(
    tmp_path: Path,
) -> None:
    result = _verify(*_chain(tmp_path))

    assert result.returncode == 0
    assert '"status": "valid"' in result.stdout
    assert '"preflight_id": "preflight-001"' in result.stdout


def test_production_deployment_verifier_rejects_checkpoint_attestation_drift(
    tmp_path: Path,
) -> None:
    chain = list(_chain(tmp_path))
    preflight_receipt = chain[4]
    deployment = chain[7]
    value = json.loads(preflight_receipt.read_text())
    value["internal_model_checkpoint"]["revision"] = "0" * 40
    _write_json(preflight_receipt, value)
    deployment_value = json.loads(deployment.read_text())
    deployment_value["preflight_receipt_sha256"] = hashlib.sha256(
        preflight_receipt.read_bytes()
    ).hexdigest()
    _write_json(deployment, deployment_value)

    result = _verify(*chain)

    assert result.returncode != 0
    assert "preflight checkpoint attestation mismatch" in result.stderr


def test_production_deployment_verifier_rejects_failed_preflight_check(
    tmp_path: Path,
) -> None:
    chain = list(_chain(tmp_path))
    preflight_receipt = chain[4]
    deployment = chain[7]
    value = json.loads(preflight_receipt.read_text())
    value["checks"]["temporal_connectivity"] = False
    _write_json(preflight_receipt, value)
    deployment_value = json.loads(deployment.read_text())
    deployment_value["preflight_receipt_sha256"] = hashlib.sha256(
        preflight_receipt.read_bytes()
    ).hexdigest()
    _write_json(deployment, deployment_value)

    result = _verify(*chain)

    assert result.returncode != 0
    assert "preflight required check failed: temporal_connectivity" in result.stderr


def test_production_deployment_verifier_rejects_tampered_preflight_contract(
    tmp_path: Path,
) -> None:
    chain = list(_chain(tmp_path))
    requirements = chain[2]
    requirements.write_text(requirements.read_text() + " ", encoding="utf-8")

    result = _verify(*chain)

    assert result.returncode != 0
    assert "runtime_preflight_contract_sha256 mismatch" in result.stderr


def test_production_deployment_verifier_rejects_tampered_receipt(
    tmp_path: Path,
) -> None:
    chain = list(_chain(tmp_path))
    receipt = chain[6]
    receipt.write_text(receipt.read_text() + " ", encoding="utf-8")

    result = _verify(*chain)

    assert result.returncode != 0
    assert "orchestrator_receipt_sha256 mismatch" in result.stderr


def test_production_deployment_verifier_rejects_receipt_image_drift(
    tmp_path: Path,
) -> None:
    chain = list(_chain(tmp_path))
    receipt = chain[6]
    deployment = chain[7]
    value = json.loads(receipt.read_text())
    value["backend_image_id"] = "sha256:" + "9" * 64
    _write_json(receipt, value)
    deployment_value = json.loads(deployment.read_text())
    deployment_value["orchestrator_receipt_sha256"] = hashlib.sha256(
        receipt.read_bytes()
    ).hexdigest()
    _write_json(deployment, deployment_value)

    result = _verify(*chain)

    assert result.returncode != 0
    assert "receipt backend_image_id mismatch" in result.stderr


def test_production_deployment_verifier_rejects_governance_drift(
    tmp_path: Path,
) -> None:
    chain = list(_chain(tmp_path))
    request = chain[5]
    deployment = chain[7]
    request_value = json.loads(request.read_text())
    request_value["governance"]["release_approval_run_id"] = "999"
    _write_json(request, request_value)
    deployment_value = json.loads(deployment.read_text())
    deployment_value["orchestrator_request_sha256"] = hashlib.sha256(
        request.read_bytes()
    ).hexdigest()
    _write_json(deployment, deployment_value)

    result = _verify(*chain)

    assert result.returncode != 0
    assert "request release approval run mismatch" in result.stderr


def test_production_deployment_verifier_rejects_bot_deployer(
    tmp_path: Path,
) -> None:
    chain = list(_chain(tmp_path))
    deployment = chain[7]
    value = json.loads(deployment.read_text())
    value["deployer"] = "deploy-bot[bot]"
    _write_json(deployment, value)

    result = _verify(*chain)

    assert result.returncode != 0
    assert "deployer must be a human GitHub actor" in result.stderr
