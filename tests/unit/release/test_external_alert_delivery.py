from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

COMMIT = "a" * 40
DEPLOYMENT_ID = "prod-20261004-001"
PROBE_ID = "hamoon-707-1"
RECEIVER = "hamoon-oncall"
INTEGRATION = "webhook"


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _metrics(total: int, failed: int) -> str:
    return (
        "# TYPE alertmanager_notifications_total counter\n"
        f'alertmanager_notifications_total{{integration="{INTEGRATION}",receiver="{RECEIVER}"}} {total}\n'
        "# TYPE alertmanager_notifications_failed_total counter\n"
        f'alertmanager_notifications_failed_total{{integration="{INTEGRATION}",receiver="{RECEIVER}",reason="other"}} {failed}\n'
    )


def _chain(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    monitoring = tmp_path / "monitoring.json"
    _write_json(
        monitoring,
        {
            "status": "BASELINE_PASSED",
            "production_deployed": True,
            "production_verified": True,
            "external_observability_backend_verified": False,
            "commit_sha": COMMIT,
            "production_monitoring_run_id": "606",
            "deployment_id": DEPLOYMENT_ID,
        },
    )

    rules = tmp_path / "rules.yml"
    rules.write_text('{"groups": []}\n', encoding="utf-8")

    status = tmp_path / "status.json"
    _write_json(
        status,
        {
            "versionInfo": {"version": "0.34.1"},
            "cluster": {"status": "ready"},
        },
    )

    route = tmp_path / "route.json"
    _write_json(
        route,
        [
            {
                "labels": {
                    "alertname": "HAMOON_ALERT_DELIVERY_PROBE",
                    "hamoon_probe_id": PROBE_ID,
                },
                "receivers": [{"name": RECEIVER}],
                "status": {"state": "active"},
            }
        ],
    )

    before = tmp_path / "before.prom"
    after = tmp_path / "after.prom"
    before.write_text(_metrics(10, 2), encoding="utf-8")
    after.write_text(_metrics(11, 2), encoding="utf-8")

    attestation = tmp_path / "attestation.json"
    _write_json(
        attestation,
        {
            "schema_version": 1,
            "status": "VERIFIED",
            "verification_scope": "EXTERNAL_ALERTMANAGER_DELIVERY",
            "external_observability_backend_verified": True,
            "alertmanager_routing_verified": True,
            "alert_delivery_verified": True,
            "production_deployed": True,
            "production_monitoring_status": "BASELINE_PASSED",
            "commit_sha": COMMIT,
            "production_monitoring_run_id": "606",
            "external_alert_delivery_run_id": "707",
            "deployment_id": DEPLOYMENT_ID,
            "alertmanager_origin": "https://alerts.example.com",
            "alertmanager_version": "0.34.1",
            "receiver": RECEIVER,
            "integration": INTEGRATION,
            "probe_id": PROBE_ID,
            "alertname": "HAMOON_ALERT_DELIVERY_PROBE",
            "runbook": "docs/runbooks/HAMOON_ALERT_DELIVERY_PROBE.md",
            "notification_total_delta": 1.0,
            "notification_failed_delta": 0.0,
            "production_monitoring_sha256": hashlib.sha256(
                monitoring.read_bytes()
            ).hexdigest(),
            "alert_rule_bundle_sha256": hashlib.sha256(
                rules.read_bytes()
            ).hexdigest(),
            "alertmanager_status_sha256": hashlib.sha256(
                status.read_bytes()
            ).hexdigest(),
            "route_observation_sha256": hashlib.sha256(
                route.read_bytes()
            ).hexdigest(),
            "metrics_before_sha256": hashlib.sha256(
                before.read_bytes()
            ).hexdigest(),
            "metrics_after_sha256": hashlib.sha256(
                after.read_bytes()
            ).hexdigest(),
            "verified_at": "2026-10-04T19:30:00+00:00",
        },
    )
    return monitoring, rules, status, route, before, after, attestation


def _verify(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/verify_external_alert_delivery.py",
            *map(str, paths),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_external_alert_delivery_accepts_routed_successful_notification(
    tmp_path: Path,
) -> None:
    result = _verify(*_chain(tmp_path))

    assert result.returncode == 0
    assert '"status": "valid"' in result.stdout


def test_external_alert_delivery_rejects_wrong_receiver(tmp_path: Path) -> None:
    chain = list(_chain(tmp_path))
    route = chain[3]
    attestation = chain[6]
    value = json.loads(route.read_text())
    value[0]["receivers"] = [{"name": "other"}]
    _write_json(route, value)
    attestation_value = json.loads(attestation.read_text())
    attestation_value["route_observation_sha256"] = hashlib.sha256(
        route.read_bytes()
    ).hexdigest()
    _write_json(attestation, attestation_value)

    result = _verify(*chain)

    assert result.returncode != 0
    assert "expected receiver" in result.stderr


def test_external_alert_delivery_rejects_notification_failure(
    tmp_path: Path,
) -> None:
    chain = list(_chain(tmp_path))
    after = chain[5]
    attestation = chain[6]
    after.write_text(_metrics(11, 3), encoding="utf-8")
    attestation_value = json.loads(attestation.read_text())
    attestation_value["metrics_after_sha256"] = hashlib.sha256(
        after.read_bytes()
    ).hexdigest()
    attestation_value["notification_failed_delta"] = 1.0
    _write_json(attestation, attestation_value)

    result = _verify(*chain)

    assert result.returncode != 0
    assert "failure counter advanced" in result.stderr


def test_external_alert_delivery_requires_receiver_labelled_metrics(
    tmp_path: Path,
) -> None:
    chain = list(_chain(tmp_path))
    before = chain[4]
    after = chain[5]
    attestation = chain[6]
    before.write_text(
        'alertmanager_notifications_total{integration="webhook"} 10\n'
        'alertmanager_notifications_failed_total{integration="webhook",reason="other"} 2\n',
        encoding="utf-8",
    )
    after.write_text(
        'alertmanager_notifications_total{integration="webhook"} 11\n'
        'alertmanager_notifications_failed_total{integration="webhook",reason="other"} 2\n',
        encoding="utf-8",
    )
    attestation_value = json.loads(attestation.read_text())
    attestation_value["metrics_before_sha256"] = hashlib.sha256(
        before.read_bytes()
    ).hexdigest()
    attestation_value["metrics_after_sha256"] = hashlib.sha256(
        after.read_bytes()
    ).hexdigest()
    _write_json(attestation, attestation_value)

    result = _verify(*chain)

    assert result.returncode != 0
    assert "receiver-labelled" in result.stderr
