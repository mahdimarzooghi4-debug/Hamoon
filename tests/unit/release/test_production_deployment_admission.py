from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

COMMIT = "a" * 40
API_IMAGE_ID = "sha256:" + "b" * 64
WEB_IMAGE_ID = "sha256:" + "c" * 64


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _chain(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    release = tmp_path / "release"
    release.mkdir()
    manifest_path = release / "manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": 2,
            "repository": "owner/Hamoon",
            "commit_sha": COMMIT,
            "workflow_run_id": "101",
            "backend": {"image_id": API_IMAGE_ID},
            "frontend": {"image_id": WEB_IMAGE_ID},
        },
    )

    stage_path = tmp_path / "stage-attestation.json"
    _write_json(
        stage_path,
        {
            "schema_version": 1,
            "status": "PASSED",
            "commit_sha": COMMIT,
            "source_ci_run_id": "101",
            "stage_admission_run_id": "202",
            "backend_image_id": API_IMAGE_ID,
            "frontend_image_id": WEB_IMAGE_ID,
        },
    )

    approval_path = tmp_path / "release-approval.json"
    _write_json(
        approval_path,
        {
            "schema_version": 1,
            "status": "APPROVED",
            "approval_scope": "RELEASE_TO_PRODUCTION",
            "authorization_only": True,
            "production_deployed": False,
            "commit_sha": COMMIT,
            "source_ci_run_id": "101",
            "stage_admission_run_id": "202",
            "approval_run_id": "303",
            "backend_image_id": API_IMAGE_ID,
            "frontend_image_id": WEB_IMAGE_ID,
            "approver": "release-admin",
            "change_reference": "REL-2026-001",
        },
    )

    readiness_path = tmp_path / "production-operational-readiness.json"
    _write_json(
        readiness_path,
        {
            "schema_version": 1,
            "status": "READY",
            "readiness_scope": "PRODUCTION_EXTERNAL_INTEGRATIONS",
            "production_deployed": False,
            "commit_sha": COMMIT,
            "workflow_run_id": "350",
            "actor": "release-admin",
            "checks": {
                "HAMOON_DEPLOY_ORCHESTRATOR_ENDPOINT": True,
                "HAMOON_PROVIDER_DISPATCH_CONFIG": True,
            },
            "checked_at": "2026-10-04T16:30:00+00:00",
        },
    )

    admission_path = tmp_path / "production-deployment-admission.json"
    _write_json(
        admission_path,
        {
            "schema_version": 1,
            "status": "ADMITTED",
            "admission_scope": "PRODUCTION_DEPLOYMENT",
            "production_deployed": False,
            "commit_sha": COMMIT,
            "source_ci_run_id": "101",
            "stage_admission_run_id": "202",
            "release_approval_run_id": "303",
            "operational_readiness_run_id": "350",
            "deployment_admission_run_id": "404",
            "release_manifest_sha256": hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest(),
            "stage_attestation_sha256": hashlib.sha256(
                stage_path.read_bytes()
            ).hexdigest(),
            "release_approval_sha256": hashlib.sha256(
                approval_path.read_bytes()
            ).hexdigest(),
            "operational_readiness_sha256": hashlib.sha256(
                readiness_path.read_bytes()
            ).hexdigest(),
            "operational_readiness_status": "READY",
            "backend_image_id": API_IMAGE_ID,
            "frontend_image_id": WEB_IMAGE_ID,
            "release_approver": "release-admin",
            "deployer": "production-operator",
            "change_reference": "REL-2026-001",
            "production_target": "hamoon-prod-primary",
            "production_endpoint": "https://hamoon.example.com",
            "expected_deployment_id": "prod-20261004-001",
            "stage_status": "PASSED",
            "release_approval_status": "APPROVED",
            "admitted_at": "2026-10-04T17:00:00+00:00",
        },
    )
    return release, stage_path, approval_path, readiness_path, admission_path


def _verify(
    release: Path,
    stage: Path,
    approval: Path,
    readiness: Path,
    admission: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/verify_production_deployment_admission.py",
            str(release),
            str(stage),
            str(approval),
            str(readiness),
            str(admission),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_production_admission_accepts_bound_approved_release(
    tmp_path: Path,
) -> None:
    chain = _chain(tmp_path)

    result = _verify(*chain)

    assert result.returncode == 0
    assert '"status": "valid"' in result.stdout


def test_production_admission_rejects_local_endpoint(tmp_path: Path) -> None:
    release, stage, approval, readiness, admission = _chain(tmp_path)
    value = json.loads(admission.read_text())
    value["production_endpoint"] = "https://localhost"
    _write_json(admission, value)

    result = _verify(release, stage, approval, readiness, admission)

    assert result.returncode != 0
    assert "non-local HTTPS endpoint" in result.stderr


def test_production_admission_rejects_unapproved_release(
    tmp_path: Path,
) -> None:
    release, stage, approval, readiness, admission = _chain(tmp_path)
    value = json.loads(approval.read_text())
    value["status"] = "DRAFT"
    _write_json(approval, value)

    result = _verify(release, stage, approval, readiness, admission)

    assert result.returncode != 0
    assert "Release Approval is not APPROVED" in result.stderr


def test_production_admission_rejects_tampered_approval(
    tmp_path: Path,
) -> None:
    release, stage, approval, readiness, admission = _chain(tmp_path)
    approval.write_text(approval.read_text() + " ", encoding="utf-8")

    result = _verify(release, stage, approval, readiness, admission)

    assert result.returncode != 0
    assert "Release Approval SHA-256 mismatch" in result.stderr


def test_production_admission_rejects_invalid_deployment_id(
    tmp_path: Path,
) -> None:
    release, stage, approval, readiness, admission = _chain(tmp_path)
    value = json.loads(admission.read_text())
    value["expected_deployment_id"] = "bad deployment id"
    _write_json(admission, value)

    result = _verify(release, stage, approval, readiness, admission)

    assert result.returncode != 0
    assert "expected_deployment_id invalid" in result.stderr


def test_production_admission_rejects_not_ready_operational_evidence(
    tmp_path: Path,
) -> None:
    release, stage, approval, readiness, admission = _chain(tmp_path)
    value = json.loads(readiness.read_text())
    value["status"] = "BLOCKED"
    _write_json(readiness, value)
    admission_value = json.loads(admission.read_text())
    admission_value["operational_readiness_sha256"] = hashlib.sha256(
        readiness.read_bytes()
    ).hexdigest()
    admission_value["operational_readiness_status"] = "BLOCKED"
    _write_json(admission, admission_value)

    result = _verify(release, stage, approval, readiness, admission)

    assert result.returncode != 0
    assert "operational readiness is not READY" in result.stderr


def test_production_admission_rejects_tampered_readiness(
    tmp_path: Path,
) -> None:
    release, stage, approval, readiness, admission = _chain(tmp_path)
    readiness.write_text(readiness.read_text() + " ", encoding="utf-8")

    result = _verify(release, stage, approval, readiness, admission)

    assert result.returncode != 0
    assert "Operational Readiness SHA-256 mismatch" in result.stderr
