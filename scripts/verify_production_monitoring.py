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
IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
DEPLOYMENT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
LABEL_RE = re.compile(r'(\w+)="((?:\\.|[^"])*)"')
FORBIDDEN_METRIC_LABELS = {
    "household_id",
    "referral_id",
    "user_id",
    "request_id",
    "trace_id",
    "national_id",
    "phone",
}
REQUIRED_WORKERS = {"outbox-worker", "temporal-worker", "provider-worker"}
REQUIRED_METRIC_FAMILIES = {
    "hamoon_http_requests_total",
    "hamoon_http_request_errors_total",
    "hamoon_http_request_duration_seconds",
    "hamoon_http_active_requests",
    "hamoon_outbox_publish_success_total",
    "hamoon_outbox_publish_failure_total",
    "hamoon_dependency_health",
    "hamoon_outbox_pending_count",
    "hamoon_outbox_oldest_age_seconds",
    "hamoon_worker_healthy",
    "hamoon_worker_heartbeat_age_seconds",
    "hamoon_operational_metrics_refresh_failures_total",
    "hamoon_provider_dispatch_success_total",
    "hamoon_provider_dispatch_failure_total",
    "hamoon_pgor_calculations_total",
    "hamoon_ai_executions_total",
    "hamoon_security_denials_total",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"production monitoring invalid: {message}")


def load_json(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"production monitoring invalid: cannot parse {path}: {exc}"
        ) from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metric_families(text: str) -> set[str]:
    families: set[str] = set()
    for line in text.splitlines():
        if line.startswith("# TYPE "):
            parts = line.split()
            if len(parts) >= 3:
                families.add(parts[2])
            continue
        if not line or line.startswith("#"):
            continue
        metric = line.split("{", 1)[0].split(" ", 1)[0]
        if metric:
            families.add(metric)
    return families


def forbidden_labels(text: str) -> set[str]:
    found: set[str] = set()
    for line in text.splitlines():
        if "{" not in line or line.startswith("#"):
            continue
        labels = line.split("{", 1)[1].split("}", 1)[0]
        for name, _value in LABEL_RE.findall(labels):
            if name in FORBIDDEN_METRIC_LABELS:
                found.add(name)
    return found


def worker_health(text: str) -> dict[str, float]:
    values: dict[str, float] = {}
    prefix = "hamoon_worker_healthy{"
    for line in text.splitlines():
        if not line.startswith(prefix):
            continue
        label_text, value_text = line.split("}", 1)
        labels = dict(LABEL_RE.findall(label_text))
        worker = labels.get("worker")
        if worker is not None:
            values[worker] = float(value_text.strip())
    return values


def request_count(text: str, *, route: str) -> float:
    total = 0.0
    prefix = "hamoon_http_requests_total{"
    for line in text.splitlines():
        if not line.startswith(prefix):
            continue
        label_text, value_text = line.split("}", 1)
        labels = dict(LABEL_RE.findall(label_text))
        if (
            labels.get("route") == route
            and labels.get("method") == "GET"
            and labels.get("status_class") == "2xx"
        ):
            total += float(value_text.strip())
    return total


def main() -> None:
    require(
        len(sys.argv) == 7,
        (
            "usage: verify_production_monitoring.py "
            "<production-verification> <backend-release> <frontend-release> "
            "<metrics-before> <metrics-after> <monitoring-attestation>"
        ),
    )

    verification_path = Path(sys.argv[1]).resolve()
    backend_path = Path(sys.argv[2]).resolve()
    frontend_path = Path(sys.argv[3]).resolve()
    before_path = Path(sys.argv[4]).resolve()
    after_path = Path(sys.argv[5]).resolve()
    monitoring_path = Path(sys.argv[6]).resolve()

    verification = load_json(verification_path)
    backend = load_json(backend_path)
    frontend = load_json(frontend_path)
    monitoring = load_json(monitoring_path)
    require(before_path.is_file(), f"missing {before_path}")
    require(after_path.is_file(), f"missing {after_path}")
    before = before_path.read_text(encoding="utf-8")
    after = after_path.read_text(encoding="utf-8")

    require(verification.get("status") == "VERIFIED", "Production not verified")
    require(
        verification.get("production_deployed") is True,
        "Production deployment not proven",
    )
    require(
        verification.get("runtime_identity_verified") is True,
        "Production runtime identity not verified",
    )

    require(monitoring.get("schema_version") == 1, "unsupported schema")
    require(
        monitoring.get("status") == "BASELINE_PASSED",
        "status must be BASELINE_PASSED",
    )
    require(
        monitoring.get("monitoring_scope")
        == "BUILTIN_PROMETHEUS_SYNTHETIC_BASELINE",
        "monitoring_scope invalid",
    )
    require(monitoring.get("production_deployed") is True, "deployment flag invalid")
    require(monitoring.get("production_verified") is True, "verification flag invalid")
    require(monitoring.get("metrics_auth_verified") is True, "metrics auth not verified")
    require(
        monitoring.get("unauthenticated_metrics_status") == 401,
        "metrics endpoint must reject unauthenticated access",
    )
    require(
        monitoring.get("external_observability_backend_verified") is False,
        "baseline must not claim external observability verification",
    )

    commit_sha = monitoring.get("commit_sha")
    require(
        isinstance(commit_sha, str) and COMMIT_RE.fullmatch(commit_sha) is not None,
        "commit_sha invalid",
    )
    require(verification.get("commit_sha") == commit_sha, "commit mismatch")

    verification_run_id = monitoring.get("production_verification_run_id")
    monitoring_run_id = monitoring.get("production_monitoring_run_id")
    require(
        verification_run_id == verification.get("production_verification_run_id"),
        "Production verification run mismatch",
    )
    require(
        isinstance(monitoring_run_id, str) and monitoring_run_id.isdigit(),
        "production_monitoring_run_id invalid",
    )

    require(
        monitoring.get("production_endpoint") == verification.get("production_endpoint"),
        "production_endpoint mismatch",
    )
    deployment_id = monitoring.get("deployment_id")
    require(
        isinstance(deployment_id, str)
        and DEPLOYMENT_ID_RE.fullmatch(deployment_id) is not None,
        "deployment_id invalid",
    )
    require(deployment_id == verification.get("deployment_id"), "deployment_id mismatch")

    for field in ("backend_image_id", "frontend_image_id"):
        value = monitoring.get(field)
        require(
            isinstance(value, str) and IMAGE_ID_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )
        require(value == verification.get(field), f"{field} mismatch")

    require(backend.get("status") == "ready", "backend not ready")
    require(backend.get("git_commit") == commit_sha, "backend commit mismatch")
    require(backend.get("image_id") == monitoring["backend_image_id"], "backend image mismatch")
    require(backend.get("deployment_id") == deployment_id, "backend deployment mismatch")

    require(frontend.get("git_commit") == commit_sha, "frontend commit mismatch")
    require(
        frontend.get("image_id") == monitoring["frontend_image_id"],
        "frontend image mismatch",
    )
    require(frontend.get("deployment_id") == deployment_id, "frontend deployment mismatch")
    require(
        frontend.get("application_version") == backend.get("application_version"),
        "application version mismatch",
    )
    require(
        monitoring.get("application_version") == backend.get("application_version"),
        "monitored application version mismatch",
    )

    migrations = backend.get("database_migration_versions")
    require(
        isinstance(migrations, list)
        and migrations
        and all(isinstance(value, str) and value for value in migrations),
        "database migration identity missing",
    )
    require(
        monitoring.get("database_migration_versions") == migrations,
        "monitored migration identity mismatch",
    )

    required_hashes = (
        ("production_verification_sha256", verification_path),
        ("metrics_before_sha256", before_path),
        ("metrics_after_sha256", after_path),
        ("backend_release_sha256", backend_path),
        ("frontend_release_sha256", frontend_path),
    )
    for field, path in required_hashes:
        value = monitoring.get(field)
        require(
            isinstance(value, str) and SHA256_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )
        require(file_sha256(path) == value, f"{field} mismatch")

    before_families = metric_families(before)
    after_families = metric_families(after)
    require(
        REQUIRED_METRIC_FAMILIES.issubset(before_families),
        "required metrics missing from baseline",
    )
    require(
        REQUIRED_METRIC_FAMILIES.issubset(after_families),
        "required metrics missing after probes",
    )
    require(not forbidden_labels(before), "forbidden metric labels in baseline")
    require(not forbidden_labels(after), "forbidden metric labels after probes")
    before_workers = worker_health(before)
    after_workers = worker_health(after)
    for worker in REQUIRED_WORKERS:
        require(
            before_workers.get(worker) == 1.0,
            f"required worker unhealthy in baseline: {worker}",
        )
        require(
            after_workers.get(worker) == 1.0,
            f"required worker unhealthy after probes: {worker}",
        )

    probe_count = monitoring.get("synthetic_ready_probe_count")
    require(
        isinstance(probe_count, int) and probe_count >= 1,
        "synthetic_ready_probe_count invalid",
    )
    before_ready = request_count(before, route="/health/ready")
    after_ready = request_count(after, route="/health/ready")
    require(
        after_ready - before_ready >= probe_count,
        "readiness telemetry did not advance with synthetic probes",
    )

    observed_at = monitoring.get("observed_at")
    require(isinstance(observed_at, str), "observed_at missing")
    try:
        timestamp = datetime.fromisoformat(observed_at)
    except ValueError as exc:
        raise SystemExit(
            "production monitoring invalid: observed_at invalid"
        ) from exc
    require(timestamp.tzinfo is not None, "observed_at must include timezone")

    print(
        json.dumps(
            {
                "status": "valid",
                "commit_sha": commit_sha,
                "deployment_id": deployment_id,
                "ready_probe_delta": after_ready - before_ready,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
