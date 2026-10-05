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


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _chain(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
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
            "governance": {
                "release_approval_run_id": "303",
                "deployment_admission_run_id": "404",
                "release_manifest_sha256": hashlib.sha256(
                    manifest.read_bytes()
                ).hexdigest(),
                "release_approval_sha256": "f" * 64,
            },
        },
    )

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
            "release_manifest_sha256": hashlib.sha256(
                manifest.read_bytes()
            ).hexdigest(),
            "release_approval_sha256": "f" * 64,
        },
    )

    request = tmp_path / "orchestrator-request.json"
    _write_json(
        request,
        {
            "schema_version": 1,
            "operation": "DEPLOY_HAMOON_RELEASE",
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
            "receipt_id": "receipt-001",
            "release_manifest_sha256": hashlib.sha256(
                manifest.read_bytes()
            ).hexdigest(),
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

    return release, admission, request, receipt, deployment


def _verify(
    release: Path,
    admission: Path,
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
            str(request),
            str(receipt),
            str(deployment),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_production_deployment_verifier_accepts_bound_receipt(
    tmp_path: Path,
) -> None:
    result = _verify(*_chain(tmp_path))

    assert result.returncode == 0
    assert '"status": "valid"' in result.stdout


def test_production_deployment_verifier_rejects_tampered_receipt(
    tmp_path: Path,
) -> None:
    release, admission, request, receipt, deployment = _chain(tmp_path)
    receipt.write_text(receipt.read_text() + " ", encoding="utf-8")

    result = _verify(release, admission, request, receipt, deployment)

    assert result.returncode != 0
    assert "orchestrator_receipt_sha256 mismatch" in result.stderr


def test_production_deployment_verifier_rejects_receipt_image_drift(
    tmp_path: Path,
) -> None:
    release, admission, request, receipt, deployment = _chain(tmp_path)
    value = json.loads(receipt.read_text())
    value["backend_image_id"] = "sha256:" + "9" * 64
    _write_json(receipt, value)
    deployment_value = json.loads(deployment.read_text())
    deployment_value["orchestrator_receipt_sha256"] = hashlib.sha256(
        receipt.read_bytes()
    ).hexdigest()
    _write_json(deployment, deployment_value)

    result = _verify(release, admission, request, receipt, deployment)

    assert result.returncode != 0
    assert "receipt backend_image_id mismatch" in result.stderr


def test_production_deployment_verifier_rejects_bot_deployer(
    tmp_path: Path,
) -> None:
    release, admission, request, receipt, deployment = _chain(tmp_path)
    value = json.loads(deployment.read_text())
    value["deployer"] = "deploy-bot[bot]"
    _write_json(deployment, value)

    result = _verify(release, admission, request, receipt, deployment)

    assert result.returncode != 0
    assert "deployer must be a human GitHub actor" in result.stderr
