from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

COMMIT = "a" * 40
API_IMAGE_ID = "sha256:" + "b" * 64
WEB_IMAGE_ID = "sha256:" + "c" * 64
DEPLOYMENT_ID = "prod-20261004-001"


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _chain(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
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
        },
    )

    backend = tmp_path / "backend-release.json"
    _write_json(
        backend,
        {
            "status": "ready",
            "service": "Hamoon",
            "environment": "production",
            "application_version": "1.2.3",
            "git_commit": COMMIT,
            "image_id": API_IMAGE_ID,
            "deployment_id": DEPLOYMENT_ID,
            "database_migration_versions": ["20261004_release_identity"],
        },
    )

    frontend = tmp_path / "frontend-release.json"
    _write_json(
        frontend,
        {
            "application_version": "1.2.3",
            "git_commit": COMMIT,
            "image_id": WEB_IMAGE_ID,
            "deployment_id": DEPLOYMENT_ID,
        },
    )

    verification = tmp_path / "production-verification.json"
    _write_json(
        verification,
        {
            "schema_version": 1,
            "status": "VERIFIED",
            "verification_scope": "HOSTED_PRODUCTION_RUNTIME",
            "production_deployed": True,
            "runtime_identity_verified": True,
            "commit_sha": COMMIT,
            "source_ci_run_id": "101",
            "stage_admission_run_id": "202",
            "release_approval_run_id": "303",
            "deployment_admission_run_id": "404",
            "production_deployment_run_id": "505",
            "production_verification_run_id": "606",
            "production_target": "hamoon-prod-primary",
            "production_endpoint": "https://hamoon.example.com",
            "deployment_id": DEPLOYMENT_ID,
            "backend_image_id": API_IMAGE_ID,
            "frontend_image_id": WEB_IMAGE_ID,
            "application_version": "1.2.3",
            "database_migration_versions": ["20261004_release_identity"],
            "deployment_admission_sha256": hashlib.sha256(
                admission.read_bytes()
            ).hexdigest(),
            "production_deployment_sha256": hashlib.sha256(
                deployment.read_bytes()
            ).hexdigest(),
            "backend_release_observation_sha256": hashlib.sha256(
                backend.read_bytes()
            ).hexdigest(),
            "frontend_release_observation_sha256": hashlib.sha256(
                frontend.read_bytes()
            ).hexdigest(),
            "verifier": "production-operator",
            "verified_at": "2026-10-04T18:00:00+00:00",
        },
    )
    return admission, deployment, backend, frontend, verification


def _verify(
    admission: Path,
    deployment: Path,
    backend: Path,
    frontend: Path,
    verification: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/verify_production_verification.py",
            str(admission),
            str(deployment),
            str(backend),
            str(frontend),
            str(verification),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_production_verification_accepts_exact_runtime_identity(
    tmp_path: Path,
) -> None:
    chain = _chain(tmp_path)

    result = _verify(*chain)

    assert result.returncode == 0
    assert '"status": "valid"' in result.stdout


def test_production_verification_rejects_stale_frontend(
    tmp_path: Path,
) -> None:
    admission, deployment, backend, frontend, verification = _chain(tmp_path)
    value = json.loads(frontend.read_text())
    value["git_commit"] = "d" * 40
    _write_json(frontend, value)

    result = _verify(admission, deployment, backend, frontend, verification)

    assert result.returncode != 0
    assert "frontend commit mismatch" in result.stderr


def test_production_verification_rejects_wrong_backend_image(
    tmp_path: Path,
) -> None:
    admission, deployment, backend, frontend, verification = _chain(tmp_path)
    value = json.loads(backend.read_text())
    value["image_id"] = "sha256:" + "e" * 64
    _write_json(backend, value)

    result = _verify(admission, deployment, backend, frontend, verification)

    assert result.returncode != 0
    assert "backend image mismatch" in result.stderr


def test_production_verification_rejects_wrong_deployment_id(
    tmp_path: Path,
) -> None:
    admission, deployment, backend, frontend, verification = _chain(tmp_path)
    value = json.loads(frontend.read_text())
    value["deployment_id"] = "prod-other"
    _write_json(frontend, value)

    result = _verify(admission, deployment, backend, frontend, verification)

    assert result.returncode != 0
    assert "frontend deployment_id mismatch" in result.stderr


def test_production_verification_rejects_missing_migration_identity(
    tmp_path: Path,
) -> None:
    admission, deployment, backend, frontend, verification = _chain(tmp_path)
    value = json.loads(backend.read_text())
    value["database_migration_versions"] = []
    _write_json(backend, value)

    result = _verify(admission, deployment, backend, frontend, verification)

    assert result.returncode != 0
    assert "database migration identity missing" in result.stderr



def test_production_verification_rejects_tampered_deployment_evidence(
    tmp_path: Path,
) -> None:
    admission, deployment, backend, frontend, verification = _chain(tmp_path)
    deployment.write_text(deployment.read_text() + " ", encoding="utf-8")

    result = _verify(admission, deployment, backend, frontend, verification)

    assert result.returncode != 0
    assert "production_deployment_sha256 mismatch" in result.stderr
