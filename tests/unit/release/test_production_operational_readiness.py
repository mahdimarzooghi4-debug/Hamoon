from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

COMMIT = "a" * 40

VALUES = {
    "HAMOON_READINESS_COMMIT_SHA": COMMIT,
    "HAMOON_READINESS_ACTOR": "release-admin",
    "HAMOON_READINESS_RUN_ID": "12345",
    "HAMOON_DEPLOY_ORCHESTRATOR_ENDPOINT": "https://deploy.example.com",
    "HAMOON_DEPLOY_ORCHESTRATOR_TOKEN": "d" * 32,
    "HAMOON_PRODUCTION_METRICS_TOKEN": "m" * 32,
    "HAMOON_OBSERVABILITY_VERIFICATION_URL": "https://obs.example.com/verify",
    "HAMOON_OBSERVABILITY_VERIFICATION_TOKEN": "obs-token",
    "HAMOON_ALERTMANAGER_URL": "https://alerts.example.com",
    "HAMOON_ALERTMANAGER_METRICS_URL": "https://alerts.example.com/metrics",
    "HAMOON_ALERTMANAGER_BEARER_TOKEN": "alert-token",
    "HAMOON_EVIDENCE_S3_ENDPOINT": "https://s3.example.com",
    "HAMOON_EVIDENCE_S3_ACCESS_KEY": "access",
    "HAMOON_EVIDENCE_S3_SECRET_KEY": "secret-value",
    "HAMOON_EVIDENCE_S3_BUCKET": "evidence",
    "HAMOON_EVIDENCE_S3_REGION": "region-1",
    "HAMOON_EVIDENCE_SCANNER_ENDPOINT": "https://scanner.example.com",
    "HAMOON_EVIDENCE_SCANNER_TOKEN": "s" * 32,
    "HAMOON_PROVIDER_DISPATCH_CONFIG": '{"mode":"configured"}',
    "HAMOON_RECOVERY_VERIFICATION_URL": "https://recovery.example.com/verify",
    "HAMOON_RECOVERY_VERIFICATION_TOKEN": "recovery-token",
}


def _run(tmp_path: Path, updates: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(VALUES)
    if updates:
        env.update(updates)
    return subprocess.run(
        [
            sys.executable,
            "scripts/verify_production_operational_readiness.py",
            str(tmp_path / "readiness.json"),
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def test_operational_readiness_attests_presence_without_secret_values(tmp_path: Path) -> None:
    result = _run(tmp_path)
    assert result.returncode == 0
    value = json.loads((tmp_path / "readiness.json").read_text())
    assert value["status"] == "READY"
    assert value["production_deployed"] is False
    assert value["commit_sha"] == COMMIT
    assert all(value["checks"].values())
    serialized = json.dumps(value)
    for secret in (
        VALUES["HAMOON_DEPLOY_ORCHESTRATOR_TOKEN"],
        VALUES["HAMOON_PRODUCTION_METRICS_TOKEN"],
        VALUES["HAMOON_EVIDENCE_S3_SECRET_KEY"],
        VALUES["HAMOON_PROVIDER_DISPATCH_CONFIG"],
    ):
        assert secret not in serialized


def test_operational_readiness_rejects_missing_required_input(tmp_path: Path) -> None:
    result = _run(tmp_path, {"HAMOON_PROVIDER_DISPATCH_CONFIG": ""})
    assert result.returncode != 0
    assert "HAMOON_PROVIDER_DISPATCH_CONFIG" in result.stderr


def test_operational_readiness_rejects_local_endpoint(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        {"HAMOON_DEPLOY_ORCHESTRATOR_ENDPOINT": "https://localhost/deploy"},
    )
    assert result.returncode != 0
    assert "remote HTTPS" in result.stderr


def test_operational_readiness_rejects_short_existing_safety_tokens(tmp_path: Path) -> None:
    result = _run(tmp_path, {"HAMOON_EVIDENCE_SCANNER_TOKEN": "short"})
    assert result.returncode != 0
    assert "evidence scanner token invalid" in result.stderr


def test_operational_readiness_workflow_is_non_deploying_and_protected() -> None:
    workflow = Path(
        ".github/workflows/production-operational-readiness.yml"
    ).read_text(encoding="utf-8")
    assert "environment: production" in workflow
    assert "scripts/verify_production_operational_readiness.py" in workflow
    assert "hamoon-production-operational-readiness-" in workflow
    assert "production-deploy.yml" not in workflow
    assert "execute_production_deployment.py" not in workflow
