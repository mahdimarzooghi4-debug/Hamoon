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
    admission = tmp_path / "rollback-admission.json"
    _write(
        admission,
        {
            "status": "ADMITTED",
            "authorization_only": True,
            "rollback_deployed": False,
            "database_strategy": "KEEP_FORWARD_SCHEMA",
            "database_downgrade_authorized": False,
            "current_commit_sha": COMMIT_CURRENT,
            "target_commit_sha": COMMIT_TARGET,
            "expected_rollback_deployment_id": "deploy-rollback-1",
            "production_target": "hamoon-prod",
            "production_endpoint": "https://hamoon.example.com",
            "production_rollback_admission_run_id": "505",
            "target_backend_image_id": IMAGE_API,
            "target_frontend_image_id": IMAGE_WEB,
            "pre_rollback_database_migration_versions": ["20261005_0030"],
        },
    )
    backend = tmp_path / "backend.json"
    _write(
        backend,
        {
            "status": "ready",
            "environment": "production",
            "git_commit": COMMIT_TARGET,
            "image_id": IMAGE_API,
            "deployment_id": "deploy-rollback-1",
            "application_version": "0.1.0",
            "database_migration_versions": ["20261005_0030"],
        },
    )
    frontend = tmp_path / "frontend.json"
    _write(
        frontend,
        {
            "git_commit": COMMIT_TARGET,
            "image_id": IMAGE_WEB,
            "deployment_id": "deploy-rollback-1",
            "application_version": "0.1.0",
        },
    )
    verification = tmp_path / "rollback-verification.json"
    _write(
        verification,
        {
            "schema_version": 1,
            "status": "VERIFIED",
            "verification_scope": "HOSTED_PRODUCTION_ROLLBACK",
            "rollback_deployed": True,
            "runtime_identity_verified": True,
            "database_schema_preserved": True,
            "database_downgrade_performed": False,
            "rolled_back_from_commit_sha": COMMIT_CURRENT,
            "commit_sha": COMMIT_TARGET,
            "deployment_id": "deploy-rollback-1",
            "production_target": "hamoon-prod",
            "production_endpoint": "https://hamoon.example.com",
            "production_rollback_admission_run_id": "505",
            "backend_image_id": IMAGE_API,
            "frontend_image_id": IMAGE_WEB,
            "database_migration_versions": ["20261005_0030"],
            "rollback_admission_sha256": hashlib.sha256(
                admission.read_bytes()
            ).hexdigest(),
            "backend_release_observation_sha256": hashlib.sha256(
                backend.read_bytes()
            ).hexdigest(),
            "frontend_release_observation_sha256": hashlib.sha256(
                frontend.read_bytes()
            ).hexdigest(),
            "production_rollback_verification_run_id": "606",
            "verifier": "operations-admin",
            "verified_at": "2026-10-05T05:05:00+00:00",
        },
    )
    return admission, backend, frontend, verification


def _verify(*paths: Path) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).parents[3] / "scripts/verify_production_rollback_verification.py"
    return subprocess.run(
        [sys.executable, str(script), *map(str, paths)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_rollback_verification_accepts_exact_runtime_identity(tmp_path: Path) -> None:
    result = _verify(*_chain(tmp_path))
    assert result.returncode == 0
    assert '"status": "valid"' in result.stdout


def test_rollback_verification_rejects_schema_change(tmp_path: Path) -> None:
    chain = list(_chain(tmp_path))
    backend = chain[1]
    verification = chain[3]
    value = json.loads(backend.read_text())
    value["database_migration_versions"] = ["20261004_0029"]
    _write(backend, value)
    verification_value = json.loads(verification.read_text())
    verification_value["backend_release_observation_sha256"] = hashlib.sha256(
        backend.read_bytes()
    ).hexdigest()
    verification_value["database_migration_versions"] = ["20261004_0029"]
    _write(verification, verification_value)
    result = _verify(*chain)
    assert result.returncode != 0
    assert "migration identity changed" in result.stderr


def test_rollback_verification_rejects_wrong_target_image(tmp_path: Path) -> None:
    chain = list(_chain(tmp_path))
    backend = chain[1]
    verification = chain[3]
    value = json.loads(backend.read_text())
    value["image_id"] = "sha256:" + "3" * 64
    _write(backend, value)
    verification_value = json.loads(verification.read_text())
    verification_value["backend_release_observation_sha256"] = hashlib.sha256(
        backend.read_bytes()
    ).hexdigest()
    verification_value["backend_image_id"] = value["image_id"]
    _write(verification, verification_value)
    result = _verify(*chain)
    assert result.returncode != 0
    assert "backend target image mismatch" in result.stderr


def test_rollback_verification_rejects_database_downgrade_claim(tmp_path: Path) -> None:
    chain = list(_chain(tmp_path))
    verification = chain[3]
    value = json.loads(verification.read_text())
    value["database_downgrade_performed"] = True
    _write(verification, value)
    result = _verify(*chain)
    assert result.returncode != 0
    assert "database downgrade" in result.stderr
