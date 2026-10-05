from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

COMMIT_CURRENT = "b" * 40
COMMIT_TARGET = "a" * 40
IMAGE_API = "sha256:" + "1" * 64
IMAGE_WEB = "sha256:" + "2" * 64


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _chain(tmp_path: Path) -> tuple[Path, ...]:
    release = tmp_path / "release"
    release.mkdir()
    manifest = release / "manifest.json"
    _write(
        manifest,
        {
            "commit_sha": COMMIT_TARGET,
            "workflow_run_id": "101",
            "backend": {"image_id": IMAGE_API},
            "frontend": {"image_id": IMAGE_WEB},
        },
    )
    stage = tmp_path / "stage.json"
    _write(
        stage,
        {
            "status": "PASSED",
            "commit_sha": COMMIT_TARGET,
            "source_ci_run_id": "101",
            "stage_admission_run_id": "202",
        },
    )
    approval = tmp_path / "approval.json"
    _write(
        approval,
        {
            "status": "APPROVED",
            "authorization_only": True,
            "commit_sha": COMMIT_TARGET,
            "source_ci_run_id": "101",
            "stage_admission_run_id": "202",
            "backend_image_id": IMAGE_API,
            "frontend_image_id": IMAGE_WEB,
        },
    )
    current = tmp_path / "current-production.json"
    _write(
        current,
        {
            "status": "VERIFIED",
            "production_deployed": True,
            "runtime_identity_verified": True,
            "commit_sha": COMMIT_CURRENT,
            "production_verification_run_id": "303",
            "production_target": "hamoon-prod",
            "production_endpoint": "https://hamoon.example.com",
            "deployment_id": "deploy-current",
            "database_migration_versions": ["20261005_0030"],
        },
    )
    admission = tmp_path / "rollback-admission.json"
    _write(
        admission,
        {
            "schema_version": 1,
            "status": "ADMITTED",
            "admission_scope": "HOSTED_PRODUCTION_ROLLBACK",
            "authorization_only": True,
            "rollback_deployed": False,
            "database_strategy": "KEEP_FORWARD_SCHEMA",
            "database_downgrade_authorized": False,
            "target_is_ancestor_of_current": True,
            "current_commit_sha": COMMIT_CURRENT,
            "target_commit_sha": COMMIT_TARGET,
            "target_source_ci_run_id": "101",
            "target_stage_admission_run_id": "202",
            "target_release_approval_run_id": "404",
            "current_production_verification_run_id": "303",
            "production_rollback_admission_run_id": "505",
            "target_backend_image_id": IMAGE_API,
            "target_frontend_image_id": IMAGE_WEB,
            "current_deployment_id": "deploy-current",
            "expected_rollback_deployment_id": "deploy-rollback-1",
            "production_target": "hamoon-prod",
            "production_endpoint": "https://hamoon.example.com",
            "pre_rollback_database_migration_versions": ["20261005_0030"],
            "target_release_manifest_sha256": hashlib.sha256(
                manifest.read_bytes()
            ).hexdigest(),
            "target_stage_attestation_sha256": hashlib.sha256(
                stage.read_bytes()
            ).hexdigest(),
            "target_release_approval_sha256": hashlib.sha256(
                approval.read_bytes()
            ).hexdigest(),
            "current_production_verification_sha256": hashlib.sha256(
                current.read_bytes()
            ).hexdigest(),
            "rollback_operator": "operations-admin",
            "change_reference": "INC-42",
            "rollback_reason": "Regression after deployment",
            "admitted_at": "2026-10-05T05:00:00+00:00",
        },
    )
    return release, stage, approval, current, admission


def _verify(*paths: Path) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).parents[3] / "scripts/verify_production_rollback_admission.py"
    return subprocess.run(
        [sys.executable, str(script), *map(str, paths)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_rollback_admission_accepts_exact_immutable_target(tmp_path: Path) -> None:
    result = _verify(*_chain(tmp_path))
    assert result.returncode == 0
    assert '"status": "valid"' in result.stdout


def test_rollback_admission_rejects_database_downgrade(tmp_path: Path) -> None:
    chain = list(_chain(tmp_path))
    admission = chain[4]
    value = json.loads(admission.read_text())
    value["database_downgrade_authorized"] = True
    _write(admission, value)
    result = _verify(*chain)
    assert result.returncode != 0
    assert "database downgrade" in result.stderr


def test_rollback_admission_rejects_non_ancestor_target(tmp_path: Path) -> None:
    chain = list(_chain(tmp_path))
    admission = chain[4]
    value = json.loads(admission.read_text())
    value["target_is_ancestor_of_current"] = False
    _write(admission, value)
    result = _verify(*chain)
    assert result.returncode != 0
    assert "target ancestry" in result.stderr


def test_rollback_admission_rejects_reused_deployment_id(tmp_path: Path) -> None:
    chain = list(_chain(tmp_path))
    admission = chain[4]
    value = json.loads(admission.read_text())
    value["expected_rollback_deployment_id"] = "deploy-current"
    _write(admission, value)
    result = _verify(*chain)
    assert result.returncode != 0
    assert "must be new" in result.stderr
