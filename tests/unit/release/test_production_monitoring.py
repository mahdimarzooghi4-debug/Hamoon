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

REQUIRED_METRICS = """# TYPE hamoon_http_requests_total counter
hamoon_http_requests_total{{route="/health/ready",method="GET",status_class="2xx"}} {ready}
# TYPE hamoon_http_request_errors_total counter
hamoon_http_request_errors_total{{route="/health/live",method="GET"}} 0
# TYPE hamoon_http_request_duration_seconds histogram
hamoon_http_request_duration_seconds_bucket{{route="/health/ready",method="GET",le="1.0"}} 1
# TYPE hamoon_http_active_requests gauge
hamoon_http_active_requests 0
# TYPE hamoon_outbox_publish_success_total counter
hamoon_outbox_publish_success_total{{event_type="TestEvent"}} 1
# TYPE hamoon_outbox_publish_failure_total counter
hamoon_outbox_publish_failure_total{{event_type="TestEvent"}} 0
# TYPE hamoon_dependency_health gauge
hamoon_dependency_health{{dependency="postgresql"}} 1
# TYPE hamoon_outbox_pending_count gauge
hamoon_outbox_pending_count 0
# TYPE hamoon_outbox_oldest_age_seconds gauge
hamoon_outbox_oldest_age_seconds 0
# TYPE hamoon_worker_healthy gauge
hamoon_worker_healthy{{worker="outbox-worker"}} 1
hamoon_worker_healthy{{worker="temporal-worker"}} 1
hamoon_worker_healthy{{worker="provider-worker"}} 1
# TYPE hamoon_worker_heartbeat_age_seconds gauge
hamoon_worker_heartbeat_age_seconds{{worker="outbox-worker"}} 5
hamoon_worker_heartbeat_age_seconds{{worker="temporal-worker"}} 5
hamoon_worker_heartbeat_age_seconds{{worker="provider-worker"}} 5
# TYPE hamoon_operational_metrics_refresh_failures_total counter
hamoon_operational_metrics_refresh_failures_total{{dependency="postgresql"}} 0
"""


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _chain(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
    verification = tmp_path / "production-verification.json"
    _write_json(
        verification,
        {
            "status": "VERIFIED",
            "production_deployed": True,
            "runtime_identity_verified": True,
            "commit_sha": COMMIT,
            "production_verification_run_id": "505",
            "production_endpoint": "https://hamoon.example.com",
            "deployment_id": DEPLOYMENT_ID,
            "backend_image_id": API_IMAGE_ID,
            "frontend_image_id": WEB_IMAGE_ID,
            "application_version": "1.2.3",
            "database_migration_versions": ["20261004_release_identity"],
        },
    )

    backend = tmp_path / "backend-release.json"
    _write_json(
        backend,
        {
            "status": "ready",
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
    before = tmp_path / "before.prom"
    after = tmp_path / "after.prom"
    before.write_text(REQUIRED_METRICS.format(ready=10), encoding="utf-8")
    after.write_text(REQUIRED_METRICS.format(ready=15), encoding="utf-8")

    monitoring = tmp_path / "monitoring.json"
    _write_json(
        monitoring,
        {
            "schema_version": 1,
            "status": "BASELINE_PASSED",
            "monitoring_scope": "BUILTIN_PROMETHEUS_SYNTHETIC_BASELINE",
            "production_deployed": True,
            "production_verified": True,
            "metrics_auth_verified": True,
            "unauthenticated_metrics_status": 401,
            "external_observability_backend_verified": False,
            "commit_sha": COMMIT,
            "production_verification_run_id": "505",
            "production_monitoring_run_id": "606",
            "production_endpoint": "https://hamoon.example.com",
            "deployment_id": DEPLOYMENT_ID,
            "backend_image_id": API_IMAGE_ID,
            "frontend_image_id": WEB_IMAGE_ID,
            "application_version": "1.2.3",
            "database_migration_versions": ["20261004_release_identity"],
            "synthetic_ready_probe_count": 5,
            "production_verification_sha256": hashlib.sha256(
                verification.read_bytes()
            ).hexdigest(),
            "metrics_before_sha256": hashlib.sha256(before.read_bytes()).hexdigest(),
            "metrics_after_sha256": hashlib.sha256(after.read_bytes()).hexdigest(),
            "backend_release_sha256": hashlib.sha256(backend.read_bytes()).hexdigest(),
            "frontend_release_sha256": hashlib.sha256(frontend.read_bytes()).hexdigest(),
            "observed_at": "2026-10-04T19:00:00+00:00",
        },
    )
    return verification, backend, frontend, before, after, monitoring


def _verify(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/verify_production_monitoring.py", *map(str, paths)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_monitoring_verifier_accepts_protected_advancing_metrics(
    tmp_path: Path,
) -> None:
    result = _verify(*_chain(tmp_path))

    assert result.returncode == 0
    assert '"status": "valid"' in result.stdout
    assert '"ready_probe_delta": 5.0' in result.stdout


def test_monitoring_verifier_rejects_stalled_telemetry(tmp_path: Path) -> None:
    chain = list(_chain(tmp_path))
    after = chain[4]
    monitoring = chain[5]
    after.write_text(REQUIRED_METRICS.format(ready=10), encoding="utf-8")
    value = json.loads(monitoring.read_text())
    value["metrics_after_sha256"] = hashlib.sha256(after.read_bytes()).hexdigest()
    _write_json(monitoring, value)

    result = _verify(*chain)

    assert result.returncode != 0
    assert "readiness telemetry did not advance" in result.stderr


def test_monitoring_verifier_rejects_sensitive_metric_label(
    tmp_path: Path,
) -> None:
    chain = list(_chain(tmp_path))
    after = chain[4]
    monitoring = chain[5]
    after.write_text(
        after.read_text()
        + 'hamoon_bad_metric{household_id="household-1"} 1\n',
        encoding="utf-8",
    )
    value = json.loads(monitoring.read_text())
    value["metrics_after_sha256"] = hashlib.sha256(after.read_bytes()).hexdigest()
    _write_json(monitoring, value)

    result = _verify(*chain)

    assert result.returncode != 0
    assert "forbidden metric labels" in result.stderr


def test_monitoring_verifier_rejects_public_metrics_boundary(
    tmp_path: Path,
) -> None:
    chain = list(_chain(tmp_path))
    monitoring = chain[5]
    value = json.loads(monitoring.read_text())
    value["unauthenticated_metrics_status"] = 200
    _write_json(monitoring, value)

    result = _verify(*chain)

    assert result.returncode != 0
    assert "reject unauthenticated access" in result.stderr


def test_monitoring_verifier_rejects_unhealthy_provider_worker(
    tmp_path: Path,
) -> None:
    chain = list(_chain(tmp_path))
    after = chain[4]
    monitoring = chain[5]
    after.write_text(
        after.read_text().replace(
            'hamoon_worker_healthy{worker="provider-worker"} 1',
            'hamoon_worker_healthy{worker="provider-worker"} 0',
        ),
        encoding="utf-8",
    )
    value = json.loads(monitoring.read_text())
    value["metrics_after_sha256"] = hashlib.sha256(after.read_bytes()).hexdigest()
    _write_json(monitoring, value)

    result = _verify(*chain)

    assert result.returncode != 0
    assert "required worker unhealthy after probes: provider-worker" in result.stderr
