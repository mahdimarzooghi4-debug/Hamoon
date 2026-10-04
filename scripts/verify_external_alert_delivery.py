#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
DEPLOYMENT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
PROBE_ID_RE = re.compile(r"^hamoon-[0-9]+-[0-9]+$")
LABEL_RE = re.compile(r'(\w+)="((?:\\.|[^"])*)"')


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"external alert delivery invalid: {message}")


def load_json(path: Path) -> object:
    require(path.is_file(), f"missing {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"external alert delivery invalid: cannot parse {path}: {exc}"
        ) from exc


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def counter_value(
    text: str,
    *,
    metric: str,
    receiver: str,
    integration: str,
) -> float | None:
    total = 0.0
    matched = False
    prefix = metric + "{"
    for line in text.splitlines():
        if not line.startswith(prefix):
            continue
        label_text, value_text = line.split("}", 1)
        labels = dict(LABEL_RE.findall(label_text))
        if (
            labels.get("receiver") == receiver
            and labels.get("integration") == integration
        ):
            total += float(value_text.strip())
            matched = True
    return total if matched else None


def main() -> None:
    require(
        len(sys.argv) == 8,
        (
            "usage: verify_external_alert_delivery.py "
            "<production-monitoring> <alert-rules> <alertmanager-status> "
            "<route-observation> <metrics-before> <metrics-after> <attestation>"
        ),
    )
    monitoring_path = Path(sys.argv[1]).resolve()
    rules_path = Path(sys.argv[2]).resolve()
    status_path = Path(sys.argv[3]).resolve()
    route_path = Path(sys.argv[4]).resolve()
    before_path = Path(sys.argv[5]).resolve()
    after_path = Path(sys.argv[6]).resolve()
    attestation_path = Path(sys.argv[7]).resolve()

    monitoring = load_json(monitoring_path)
    status = load_json(status_path)
    route = load_json(route_path)
    attestation = load_json(attestation_path)

    require(isinstance(monitoring, dict), "Production monitoring must be an object")
    require(isinstance(status, dict), "Alertmanager status must be an object")
    require(isinstance(route, list), "route observation must be an alert list")
    require(isinstance(attestation, dict), "attestation must be an object")
    require(rules_path.is_file(), "alert rule bundle missing")
    require(before_path.is_file(), "metrics-before missing")
    require(after_path.is_file(), "metrics-after missing")

    require(monitoring.get("status") == "BASELINE_PASSED", "monitoring baseline not passed")
    require(monitoring.get("production_deployed") is True, "Production not deployed")
    require(monitoring.get("production_verified") is True, "Production not verified")
    require(
        monitoring.get("external_observability_backend_verified") is False,
        "baseline unexpectedly claims external backend verification",
    )

    require(attestation.get("schema_version") == 1, "unsupported schema")
    require(attestation.get("status") == "VERIFIED", "status must be VERIFIED")
    require(
        attestation.get("verification_scope") == "EXTERNAL_ALERTMANAGER_DELIVERY",
        "verification_scope invalid",
    )
    require(
        attestation.get("external_observability_backend_verified") is True,
        "external backend must be verified",
    )
    require(
        attestation.get("alertmanager_routing_verified") is True,
        "Alertmanager routing must be verified",
    )
    require(
        attestation.get("alert_delivery_verified") is True,
        "alert delivery must be verified",
    )
    require(attestation.get("production_deployed") is True, "deployment flag invalid")
    require(
        attestation.get("production_monitoring_status") == "BASELINE_PASSED",
        "monitoring status mismatch",
    )

    commit_sha = attestation.get("commit_sha")
    require(
        isinstance(commit_sha, str) and COMMIT_RE.fullmatch(commit_sha) is not None,
        "commit_sha invalid",
    )
    require(monitoring.get("commit_sha") == commit_sha, "commit mismatch")

    monitoring_run_id = attestation.get("production_monitoring_run_id")
    external_run_id = attestation.get("external_alert_delivery_run_id")
    require(
        monitoring_run_id == monitoring.get("production_monitoring_run_id"),
        "Production monitoring run mismatch",
    )
    require(
        isinstance(external_run_id, str) and external_run_id.isdigit(),
        "external alert delivery run id invalid",
    )

    deployment_id = attestation.get("deployment_id")
    require(
        isinstance(deployment_id, str)
        and DEPLOYMENT_ID_RE.fullmatch(deployment_id) is not None,
        "deployment_id invalid",
    )
    require(deployment_id == monitoring.get("deployment_id"), "deployment mismatch")

    origin = attestation.get("alertmanager_origin")
    require(
        isinstance(origin, str) and origin.startswith("https://"),
        "Alertmanager origin must use HTTPS",
    )

    version_info = status.get("versionInfo")
    require(isinstance(version_info, dict), "Alertmanager versionInfo missing")
    version = version_info.get("version")
    require(isinstance(version, str) and version, "Alertmanager version missing")
    require(
        attestation.get("alertmanager_version") == version,
        "Alertmanager version mismatch",
    )

    receiver = attestation.get("receiver")
    integration = attestation.get("integration")
    require(isinstance(receiver, str) and receiver, "receiver missing")
    require(isinstance(integration, str) and integration, "integration missing")

    probe_id = attestation.get("probe_id")
    require(
        isinstance(probe_id, str) and PROBE_ID_RE.fullmatch(probe_id) is not None,
        "probe_id invalid",
    )
    require(
        attestation.get("alertname") == "HAMOON_ALERT_DELIVERY_PROBE",
        "alertname invalid",
    )
    require(
        attestation.get("runbook")
        == "docs/runbooks/HAMOON_ALERT_DELIVERY_PROBE.md",
        "probe runbook invalid",
    )

    routed = False
    for raw in route:
        if not isinstance(raw, dict):
            continue
        labels = raw.get("labels")
        receivers = raw.get("receivers")
        state = raw.get("status")
        if not isinstance(labels, dict) or not isinstance(receivers, list):
            continue
        receiver_names = {
            item.get("name")
            for item in receivers
            if isinstance(item, dict)
        }
        if (
            labels.get("alertname") == "HAMOON_ALERT_DELIVERY_PROBE"
            and labels.get("hamoon_probe_id") == probe_id
            and isinstance(state, dict)
            and state.get("state") == "active"
            and receiver in receiver_names
        ):
            routed = True
            break
    require(routed, "probe did not route to expected receiver")

    before = before_path.read_text(encoding="utf-8")
    after = after_path.read_text(encoding="utf-8")
    before_total = counter_value(
        before,
        metric="alertmanager_notifications_total",
        receiver=receiver,
        integration=integration,
    )
    after_total = counter_value(
        after,
        metric="alertmanager_notifications_total",
        receiver=receiver,
        integration=integration,
    )
    before_failed = counter_value(
        before,
        metric="alertmanager_notifications_failed_total",
        receiver=receiver,
        integration=integration,
    )
    after_failed = counter_value(
        after,
        metric="alertmanager_notifications_failed_total",
        receiver=receiver,
        integration=integration,
    )
    require(
        None not in (before_total, after_total, before_failed, after_failed),
        "receiver-labelled Alertmanager notification metrics unavailable",
    )
    assert before_total is not None
    assert after_total is not None
    assert before_failed is not None
    assert after_failed is not None

    total_delta = after_total - before_total
    failed_delta = after_failed - before_failed
    require(total_delta >= 1, "notification counter did not advance")
    require(failed_delta == 0, "notification failure counter advanced")
    require(
        attestation.get("notification_total_delta") == total_delta,
        "notification_total_delta mismatch",
    )
    require(
        attestation.get("notification_failed_delta") == failed_delta,
        "notification_failed_delta mismatch",
    )

    hashes = (
        ("production_monitoring_sha256", monitoring_path),
        ("alert_rule_bundle_sha256", rules_path),
        ("alertmanager_status_sha256", status_path),
        ("route_observation_sha256", route_path),
        ("metrics_before_sha256", before_path),
        ("metrics_after_sha256", after_path),
    )
    for field, path in hashes:
        value = attestation.get(field)
        require(
            isinstance(value, str) and SHA256_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )
        require(file_sha256(path) == value, f"{field} mismatch")

    verified_at = attestation.get("verified_at")
    require(isinstance(verified_at, str), "verified_at missing")
    try:
        timestamp = datetime.fromisoformat(verified_at)
    except ValueError as exc:
        raise SystemExit(
            "external alert delivery invalid: verified_at invalid"
        ) from exc
    require(timestamp.tzinfo is not None, "verified_at must include timezone")

    print(
        json.dumps(
            {
                "status": "valid",
                "commit_sha": commit_sha,
                "receiver": receiver,
                "integration": integration,
                "notification_total_delta": total_delta,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
