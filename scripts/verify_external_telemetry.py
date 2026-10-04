#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
DEPLOYMENT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
PROBE_ID_RE = re.compile(r"^hamoon-otel-[0-9a-f]{32}$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"external telemetry invalid: {message}")


def load_object(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"external telemetry invalid: cannot parse {path}: {exc}"
        ) from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def remote_https(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or parsed.hostname is None:
        return False
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_unspecified
    )


def parse_timestamp(value: object, field: str) -> datetime:
    require(isinstance(value, str), f"{field} missing")
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"external telemetry invalid: {field} invalid") from exc
    require(timestamp.tzinfo is not None, f"{field} must include timezone")
    return timestamp


def recursive_keys(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            found.add(str(key).lower())
            found.update(recursive_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            found.update(recursive_keys(nested))
    return found


def require_resource(
    *,
    resource: object,
    policy: dict[str, object],
    monitoring: dict[str, object],
    observation_name: str,
) -> dict[str, object]:
    require(isinstance(resource, dict), f"{observation_name} resource missing")
    required = policy.get("required_resource_attributes")
    require(isinstance(required, list), "required_resource_attributes invalid")
    for name in required:
        require(
            isinstance(name, str) and name in resource,
            f"{observation_name} resource missing {name}",
        )

    require(
        resource.get("service.name") == "hamoon-api",
        f"{observation_name} service.name mismatch",
    )
    require(
        resource.get("deployment.environment.name") in {"prod", "production"},
        f"{observation_name} environment mismatch",
    )
    require(
        resource.get("service.version") == monitoring.get("application_version"),
        f"{observation_name} service.version mismatch",
    )
    require(
        resource.get("hamoon.git_commit") == monitoring.get("commit_sha"),
        f"{observation_name} commit mismatch",
    )
    require(
        resource.get("hamoon.image_id") == monitoring.get("backend_image_id"),
        f"{observation_name} image mismatch",
    )
    require(
        resource.get("hamoon.deployment_id") == monitoring.get("deployment_id"),
        f"{observation_name} deployment mismatch",
    )
    return resource


def main() -> None:
    require(
        len(sys.argv) == 6,
        (
            "usage: verify_external_telemetry.py "
            "<policy> <production-monitoring> <probe-response> "
            "<backend-observation> <attestation>"
        ),
    )
    policy_path = Path(sys.argv[1]).resolve()
    monitoring_path = Path(sys.argv[2]).resolve()
    probe_path = Path(sys.argv[3]).resolve()
    observation_path = Path(sys.argv[4]).resolve()
    attestation_path = Path(sys.argv[5]).resolve()

    policy = load_object(policy_path)
    monitoring = load_object(monitoring_path)
    probe = load_object(probe_path)
    observation = load_object(observation_path)
    attestation = load_object(attestation_path)

    require(policy.get("schema_version") == 1, "policy schema unsupported")
    require(policy.get("status") == "ENFORCED", "policy not enforced")
    require(monitoring.get("status") == "BASELINE_PASSED", "monitoring baseline not passed")
    require(monitoring.get("production_deployed") is True, "Production not deployed")
    require(monitoring.get("production_verified") is True, "Production not verified")

    commit_sha = monitoring.get("commit_sha")
    deployment_id = monitoring.get("deployment_id")
    backend_image_id = monitoring.get("backend_image_id")
    require(
        isinstance(commit_sha, str) and COMMIT_RE.fullmatch(commit_sha) is not None,
        "monitoring commit invalid",
    )
    require(
        isinstance(deployment_id, str)
        and DEPLOYMENT_ID_RE.fullmatch(deployment_id) is not None,
        "monitoring deployment invalid",
    )
    require(
        isinstance(backend_image_id, str)
        and IMAGE_ID_RE.fullmatch(backend_image_id) is not None,
        "monitoring backend image invalid",
    )

    require(probe.get("status") == "emitted", "probe was not emitted")
    probe_id = probe.get("probe_id")
    trace_id = probe.get("trace_id")
    require(
        isinstance(probe_id, str) and PROBE_ID_RE.fullmatch(probe_id) is not None,
        "probe_id invalid",
    )
    require(
        isinstance(trace_id, str) and TRACE_ID_RE.fullmatch(trace_id) is not None,
        "trace_id invalid",
    )
    require(probe.get("git_commit") == commit_sha, "probe commit mismatch")
    require(probe.get("deployment_id") == deployment_id, "probe deployment mismatch")
    require(
        str(probe.get("environment", "")).lower() in {"prod", "production"},
        "probe environment is not Production",
    )

    require(observation.get("schema_version") == 1, "observation schema unsupported")
    provider = observation.get("provider")
    require(isinstance(provider, str) and provider.strip(), "provider missing")
    require(remote_https(observation.get("query_origin")), "query_origin must be remote HTTPS")
    require(observation.get("probe_id") == probe_id, "observation probe mismatch")
    require(observation.get("trace_id") == trace_id, "observation trace mismatch")
    require(observation.get("commit_sha") == commit_sha, "observation commit mismatch")
    require(
        observation.get("deployment_id") == deployment_id,
        "observation deployment mismatch",
    )

    forbidden = policy.get("forbidden_evidence_fields")
    require(isinstance(forbidden, list), "forbidden_evidence_fields invalid")
    evidence_keys = recursive_keys(observation)
    leaked = {str(name).lower() for name in forbidden} & evidence_keys
    require(not leaked, f"forbidden evidence fields present {sorted(leaked)}")

    probe_policy = policy.get("probe")
    require(isinstance(probe_policy, dict), "probe policy missing")

    trace_observation = observation.get("trace")
    require(isinstance(trace_observation, dict), "trace observation missing")
    require(trace_observation.get("found") is True, "trace not found")
    require(
        trace_observation.get("span_name") == probe_policy.get("span_name"),
        "probe span name mismatch",
    )
    require(trace_observation.get("trace_id") == trace_id, "trace query id mismatch")
    require_resource(
        resource=trace_observation.get("resource"),
        policy=policy,
        monitoring=monitoring,
        observation_name="trace",
    )

    log_observation = observation.get("log")
    require(isinstance(log_observation, dict), "log observation missing")
    require(log_observation.get("found") is True, "log not found")
    require(log_observation.get("trace_id") == trace_id, "log trace correlation mismatch")
    require(
        log_observation.get("body") == probe_policy.get("log_message"),
        "probe log body mismatch",
    )
    attributes = log_observation.get("attributes")
    require(isinstance(attributes, dict), "probe log attributes missing")
    require(attributes.get("event_id") == probe_id, "probe log event_id mismatch")
    require(
        attributes.get("operation") == probe_policy.get("log_operation"),
        "probe log operation mismatch",
    )
    require_resource(
        resource=log_observation.get("resource"),
        policy=policy,
        monitoring=monitoring,
        observation_name="log",
    )

    retention = observation.get("retention")
    require(isinstance(retention, dict), "retention observation missing")
    minimum = policy.get("minimum_retention_days")
    require(isinstance(minimum, dict), "minimum_retention_days invalid")
    for signal in ("traces", "logs"):
        actual = retention.get(f"{signal}_days")
        required = minimum.get(signal)
        require(
            isinstance(actual, int) and isinstance(required, int) and actual >= required,
            f"{signal} retention below policy",
        )
    require(
        remote_https(retention.get("evidence_url")),
        "retention evidence_url must be remote HTTPS",
    )

    dashboards = observation.get("dashboards")
    require(isinstance(dashboards, list), "dashboard observation missing")
    dashboard_map = {
        item.get("id"): item
        for item in dashboards
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    required_dashboards = policy.get("required_dashboards")
    require(isinstance(required_dashboards, list), "required_dashboards invalid")
    for required_dashboard in required_dashboards:
        require(isinstance(required_dashboard, dict), "required dashboard invalid")
        dashboard_id = required_dashboard.get("id")
        require(isinstance(dashboard_id, str), "required dashboard id invalid")
        actual = dashboard_map.get(dashboard_id)
        require(isinstance(actual, dict), f"dashboard {dashboard_id} missing")
        require(actual.get("status") == "available", f"dashboard {dashboard_id} unavailable")
        require(
            remote_https(actual.get("url")),
            f"dashboard {dashboard_id} URL must be remote HTTPS",
        )

    observed_at = parse_timestamp(observation.get("observed_at"), "observed_at")

    require(attestation.get("schema_version") == 1, "attestation schema unsupported")
    require(attestation.get("status") == "VERIFIED", "attestation status invalid")
    require(
        attestation.get("verification_scope") == "EXTERNAL_OTEL_TRACES_LOGS",
        "verification_scope invalid",
    )
    require(
        attestation.get("external_telemetry_backend_verified") is True,
        "external telemetry backend not verified",
    )
    require(attestation.get("trace_ingestion_verified") is True, "trace verification flag invalid")
    require(attestation.get("log_ingestion_verified") is True, "log verification flag invalid")
    require(attestation.get("retention_verified") is True, "retention verification flag invalid")
    require(attestation.get("dashboards_verified") is True, "dashboard verification flag invalid")
    require(attestation.get("commit_sha") == commit_sha, "attestation commit mismatch")
    require(attestation.get("deployment_id") == deployment_id, "attestation deployment mismatch")
    require(attestation.get("probe_id") == probe_id, "attestation probe mismatch")
    require(attestation.get("trace_id") == trace_id, "attestation trace mismatch")
    require(attestation.get("provider") == provider, "attestation provider mismatch")
    require(
        attestation.get("production_monitoring_run_id")
        == monitoring.get("production_monitoring_run_id"),
        "Production monitoring run mismatch",
    )
    external_run_id = attestation.get("external_telemetry_run_id")
    require(
        isinstance(external_run_id, str) and external_run_id.isdigit(),
        "external telemetry run id invalid",
    )
    require(
        attestation.get("minimum_trace_retention_days") == minimum.get("traces"),
        "trace retention policy mismatch",
    )
    require(
        attestation.get("minimum_log_retention_days") == minimum.get("logs"),
        "log retention policy mismatch",
    )
    require(
        set(attestation.get("dashboard_ids", []))
        == {str(item["id"]) for item in required_dashboards},
        "dashboard attestation mismatch",
    )

    hashes = (
        ("policy_sha256", policy_path),
        ("production_monitoring_sha256", monitoring_path),
        ("probe_response_sha256", probe_path),
        ("backend_observation_sha256", observation_path),
    )
    for field, path in hashes:
        value = attestation.get(field)
        require(
            isinstance(value, str) and SHA256_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )
        require(file_sha256(path) == value, f"{field} mismatch")

    verified_at = parse_timestamp(attestation.get("verified_at"), "verified_at")
    require(verified_at >= observed_at, "attestation predates backend observation")

    print(
        json.dumps(
            {
                "status": "valid",
                "commit_sha": commit_sha,
                "provider": provider,
                "probe_id": probe_id,
                "dashboard_count": len(required_dashboards),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
