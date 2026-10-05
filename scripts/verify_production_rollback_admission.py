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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"production rollback admission invalid: {message}")


def load_json(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"production rollback admission invalid: cannot parse {path}: {exc}"
        ) from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def digest(path: Path) -> str:
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
        raise SystemExit(
            f"production rollback admission invalid: {field} invalid"
        ) from exc
    require(timestamp.tzinfo is not None, f"{field} must include timezone")
    return timestamp


def nonempty_str(value: object, field: str) -> str:
    require(isinstance(value, str) and value.strip(), f"{field} missing")
    return value.strip()


def main() -> None:
    require(
        len(sys.argv) == 6,
        (
            "usage: verify_production_rollback_admission.py "
            "<target-release-dir> <target-stage> <target-approval> "
            "<current-production-verification> <rollback-admission>"
        ),
    )

    release_dir = Path(sys.argv[1]).resolve()
    stage_path = Path(sys.argv[2]).resolve()
    approval_path = Path(sys.argv[3]).resolve()
    current_path = Path(sys.argv[4]).resolve()
    admission_path = Path(sys.argv[5]).resolve()

    manifest_path = release_dir / "manifest.json"
    manifest = load_json(manifest_path)
    stage = load_json(stage_path)
    approval = load_json(approval_path)
    current = load_json(current_path)
    admission = load_json(admission_path)

    require(stage.get("status") == "PASSED", "target Stage admission not passed")
    require(approval.get("status") == "APPROVED", "target release not approved")
    require(
        approval.get("authorization_only") is True,
        "target release approval must remain authorization-only",
    )
    require(current.get("status") == "VERIFIED", "current Production not verified")
    require(current.get("production_deployed") is True, "current Production not deployed")
    require(
        current.get("runtime_identity_verified") is True,
        "current Production runtime identity not verified",
    )

    require(admission.get("schema_version") == 1, "unsupported schema")
    require(admission.get("status") == "ADMITTED", "status must be ADMITTED")
    require(
        admission.get("admission_scope") == "HOSTED_PRODUCTION_ROLLBACK",
        "admission_scope invalid",
    )
    require(
        admission.get("authorization_only") is True,
        "rollback admission must be authorization-only",
    )
    require(
        admission.get("rollback_deployed") is False,
        "rollback admission must precede deployment evidence",
    )
    require(
        admission.get("database_downgrade_authorized") is False,
        "database downgrade must not be authorized",
    )
    require(
        admission.get("database_strategy") == "KEEP_FORWARD_SCHEMA",
        "database strategy must preserve current schema",
    )
    require(
        admission.get("target_is_ancestor_of_current") is True,
        "target ancestry must be verified",
    )

    current_commit = admission.get("current_commit_sha")
    target_commit = admission.get("target_commit_sha")
    for value, field in (
        (current_commit, "current_commit_sha"),
        (target_commit, "target_commit_sha"),
    ):
        require(
            isinstance(value, str) and COMMIT_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )
    require(current_commit != target_commit, "rollback target must differ from current")
    require(current.get("commit_sha") == current_commit, "current commit mismatch")
    require(manifest.get("commit_sha") == target_commit, "target manifest commit mismatch")
    require(stage.get("commit_sha") == target_commit, "target Stage commit mismatch")
    require(approval.get("commit_sha") == target_commit, "target approval commit mismatch")

    source_run_id = admission.get("target_source_ci_run_id")
    stage_run_id = admission.get("target_stage_admission_run_id")
    approval_run_id = admission.get("target_release_approval_run_id")
    current_verification_run_id = admission.get("current_production_verification_run_id")
    rollback_run_id = admission.get("production_rollback_admission_run_id")
    for value, field in (
        (source_run_id, "target_source_ci_run_id"),
        (stage_run_id, "target_stage_admission_run_id"),
        (approval_run_id, "target_release_approval_run_id"),
        (current_verification_run_id, "current_production_verification_run_id"),
        (rollback_run_id, "production_rollback_admission_run_id"),
    ):
        require(isinstance(value, str) and value.isdigit(), f"{field} invalid")

    require(manifest.get("workflow_run_id") == source_run_id, "target source CI mismatch")
    require(stage.get("source_ci_run_id") == source_run_id, "target Stage source mismatch")
    require(
        stage.get("stage_admission_run_id") == stage_run_id,
        "target Stage run mismatch",
    )
    require(approval.get("source_ci_run_id") == source_run_id, "target approval source mismatch")
    require(
        approval.get("stage_admission_run_id") == stage_run_id,
        "target approval Stage mismatch",
    )
    require(
        current.get("production_verification_run_id") == current_verification_run_id,
        "current Production verification run mismatch",
    )

    backend = manifest.get("backend")
    frontend = manifest.get("frontend")
    require(isinstance(backend, dict), "target backend manifest missing")
    require(isinstance(frontend, dict), "target frontend manifest missing")
    backend_image = admission.get("target_backend_image_id")
    frontend_image = admission.get("target_frontend_image_id")
    for value, field in (
        (backend_image, "target_backend_image_id"),
        (frontend_image, "target_frontend_image_id"),
    ):
        require(
            isinstance(value, str) and IMAGE_ID_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )
    require(backend.get("image_id") == backend_image, "target backend image mismatch")
    require(frontend.get("image_id") == frontend_image, "target frontend image mismatch")
    require(approval.get("backend_image_id") == backend_image, "approved backend image mismatch")
    require(approval.get("frontend_image_id") == frontend_image, "approved frontend image mismatch")

    current_deployment = admission.get("current_deployment_id")
    expected_rollback_deployment = admission.get("expected_rollback_deployment_id")
    for value, field in (
        (current_deployment, "current_deployment_id"),
        (expected_rollback_deployment, "expected_rollback_deployment_id"),
    ):
        require(
            isinstance(value, str) and DEPLOYMENT_ID_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )
    require(
        current.get("deployment_id") == current_deployment,
        "current deployment mismatch",
    )
    require(
        expected_rollback_deployment != current_deployment,
        "rollback deployment id must be new",
    )

    require(
        admission.get("production_target") == current.get("production_target"),
        "production target mismatch",
    )
    endpoint = admission.get("production_endpoint")
    require(endpoint == current.get("production_endpoint"), "production endpoint mismatch")
    require(remote_https(endpoint), "production endpoint must be remote HTTPS")

    migrations = admission.get("pre_rollback_database_migration_versions")
    require(
        isinstance(migrations, list)
        and migrations
        and all(isinstance(value, str) and value for value in migrations),
        "pre-rollback migration identity missing",
    )
    require(
        current.get("database_migration_versions") == migrations,
        "pre-rollback migration identity mismatch",
    )

    for field, path in (
        ("target_release_manifest_sha256", manifest_path),
        ("target_stage_attestation_sha256", stage_path),
        ("target_release_approval_sha256", approval_path),
        ("current_production_verification_sha256", current_path),
    ):
        value = admission.get(field)
        require(
            isinstance(value, str) and SHA256_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )
        require(value == digest(path), f"{field} mismatch")

    operator = admission.get("rollback_operator")
    require(
        isinstance(operator, str) and operator and not operator.endswith("[bot]"),
        "rollback_operator must be a human GitHub actor",
    )
    nonempty_str(admission.get("change_reference"), "change_reference")
    nonempty_str(admission.get("rollback_reason"), "rollback_reason")
    parse_timestamp(admission.get("admitted_at"), "admitted_at")

    print(
        json.dumps(
            {
                "status": "valid",
                "current_commit_sha": current_commit,
                "target_commit_sha": target_commit,
                "expected_rollback_deployment_id": expected_rollback_deployment,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
