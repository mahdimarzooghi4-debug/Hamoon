from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

COMMIT = "a" * 40
IMAGE_ID = "sha256:" + "b" * 64
DEPLOYMENT_ID = "prod-20261004-001"
PROBE_ID = "hamoon-otel-" + "c" * 32
TRACE_ID = "d" * 32
POLICY = Path("ops/observability/external-telemetry-policy.json")


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _resource() -> dict[str, object]:
    return {
        "service.name": "hamoon-api",
        "service.version": "1.2.3",
        "deployment.environment.name": "production",
        "hamoon.git_commit": COMMIT,
        "hamoon.image_id": IMAGE_ID,
        "hamoon.deployment_id": DEPLOYMENT_ID,
    }


def _chain(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    monitoring = tmp_path / "monitoring.json"
    _write_json(
        monitoring,
        {
            "status": "BASELINE_PASSED",
            "production_deployed": True,
            "production_verified": True,
            "commit_sha": COMMIT,
            "production_monitoring_run_id": "606",
            "deployment_id": DEPLOYMENT_ID,
            "backend_image_id": IMAGE_ID,
            "application_version": "1.2.3",
        },
    )

    probe = tmp_path / "probe.json"
    _write_json(
        probe,
        {
            "status": "emitted",
            "probe_id": PROBE_ID,
            "trace_id": TRACE_ID,
            "span_id": "e" * 16,
            "service": "hamoon-api",
            "environment": "production",
            "git_commit": COMMIT,
            "deployment_id": DEPLOYMENT_ID,
        },
    )

    observation = tmp_path / "observation.json"
    _write_json(
        observation,
        {
            "schema_version": 1,
            "provider": "example-observability",
            "query_origin": "https://observability.example.com",
            "probe_id": PROBE_ID,
            "trace_id": TRACE_ID,
            "commit_sha": COMMIT,
            "deployment_id": DEPLOYMENT_ID,
            "trace": {
                "found": True,
                "span_name": "hamoon.observability.probe",
                "trace_id": TRACE_ID,
                "resource": _resource(),
            },
            "log": {
                "found": True,
                "trace_id": TRACE_ID,
                "body": "Observability verification probe emitted",
                "attributes": {
                    "event_id": PROBE_ID,
                    "operation": "observability_probe",
                },
                "resource": _resource(),
            },
            "retention": {
                "traces_days": 30,
                "logs_days": 60,
                "evidence_url": "https://observability.example.com/retention",
            },
            "dashboards": [
                {
                    "id": "platform",
                    "status": "available",
                    "url": "https://observability.example.com/d/platform",
                },
                {
                    "id": "async-workers",
                    "status": "available",
                    "url": "https://observability.example.com/d/workers",
                },
            ],
            "observed_at": "2026-10-04T20:00:00+00:00",
        },
    )

    policy = json.loads(POLICY.read_text())
    attestation = tmp_path / "attestation.json"
    _write_json(
        attestation,
        {
            "schema_version": 1,
            "status": "VERIFIED",
            "verification_scope": "EXTERNAL_OTEL_TRACES_LOGS",
            "external_telemetry_backend_verified": True,
            "trace_ingestion_verified": True,
            "log_ingestion_verified": True,
            "retention_verified": True,
            "dashboards_verified": True,
            "commit_sha": COMMIT,
            "deployment_id": DEPLOYMENT_ID,
            "probe_id": PROBE_ID,
            "trace_id": TRACE_ID,
            "provider": "example-observability",
            "production_monitoring_run_id": "606",
            "external_telemetry_run_id": "808",
            "minimum_trace_retention_days": policy[
                "minimum_retention_days"
            ]["traces"],
            "minimum_log_retention_days": policy[
                "minimum_retention_days"
            ]["logs"],
            "dashboard_ids": [
                item["id"] for item in policy["required_dashboards"]
            ],
            "policy_sha256": hashlib.sha256(
                POLICY.read_bytes()
            ).hexdigest(),
            "production_monitoring_sha256": hashlib.sha256(
                monitoring.read_bytes()
            ).hexdigest(),
            "probe_response_sha256": hashlib.sha256(
                probe.read_bytes()
            ).hexdigest(),
            "backend_observation_sha256": hashlib.sha256(
                observation.read_bytes()
            ).hexdigest(),
            "verified_at": "2026-10-04T20:01:00+00:00",
        },
    )
    return POLICY, monitoring, probe, observation, attestation


def _refresh_observation_hash(observation: Path, attestation: Path) -> None:
    value = json.loads(attestation.read_text())
    value["backend_observation_sha256"] = hashlib.sha256(
        observation.read_bytes()
    ).hexdigest()
    _write_json(attestation, value)


def _verify(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/verify_external_telemetry.py",
            *map(str, paths),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_external_telemetry_accepts_correlated_trace_log_retention_dashboards(
    tmp_path: Path,
) -> None:
    result = _verify(*_chain(tmp_path))

    assert result.returncode == 0
    assert '"status": "valid"' in result.stdout


def test_external_telemetry_rejects_missing_log(tmp_path: Path) -> None:
    chain = list(_chain(tmp_path))
    observation = chain[3]
    attestation = chain[4]
    value = json.loads(observation.read_text())
    value["log"]["found"] = False
    _write_json(observation, value)
    _refresh_observation_hash(observation, attestation)

    result = _verify(*chain)

    assert result.returncode != 0
    assert "log not found" in result.stderr


def test_external_telemetry_rejects_retention_below_policy(
    tmp_path: Path,
) -> None:
    chain = list(_chain(tmp_path))
    observation = chain[3]
    attestation = chain[4]
    value = json.loads(observation.read_text())
    value["retention"]["traces_days"] = 1
    _write_json(observation, value)
    _refresh_observation_hash(observation, attestation)

    result = _verify(*chain)

    assert result.returncode != 0
    assert "traces retention below policy" in result.stderr


def test_external_telemetry_rejects_unavailable_dashboard(
    tmp_path: Path,
) -> None:
    chain = list(_chain(tmp_path))
    observation = chain[3]
    attestation = chain[4]
    value = json.loads(observation.read_text())
    value["dashboards"][0]["status"] = "missing"
    _write_json(observation, value)
    _refresh_observation_hash(observation, attestation)

    result = _verify(*chain)

    assert result.returncode != 0
    assert "dashboard platform unavailable" in result.stderr


def test_external_telemetry_rejects_sensitive_evidence_fields(
    tmp_path: Path,
) -> None:
    chain = list(_chain(tmp_path))
    observation = chain[3]
    attestation = chain[4]
    value = json.loads(observation.read_text())
    value["trace"]["household_id"] = "household-1"
    _write_json(observation, value)
    _refresh_observation_hash(observation, attestation)

    result = _verify(*chain)

    assert result.returncode != 0
    assert "forbidden evidence fields" in result.stderr
