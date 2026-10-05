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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"production rollback verification invalid: {message}")


def load_json(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"production rollback verification invalid: cannot parse {path}: {exc}"
        ) from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_timestamp(value: object, field: str) -> datetime:
    require(isinstance(value, str), f"{field} missing")
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(
            f"production rollback verification invalid: {field} invalid"
        ) from exc
    require(timestamp.tzinfo is not None, f"{field} must include timezone")
    return timestamp


def main() -> None:
    require(
        len(sys.argv) == 5,
        (
            "usage: verify_production_rollback_verification.py "
            "<rollback-admission> <backend-release> <frontend-release> "
            "<rollback-verification>"
        ),
    )

    admission_path = Path(sys.argv[1]).resolve()
    backend_path = Path(sys.argv[2]).resolve()
    frontend_path = Path(sys.argv[3]).resolve()
    verification_path = Path(sys.argv[4]).resolve()

    admission = load_json(admission_path)
    backend = load_json(backend_path)
    frontend = load_json(frontend_path)
    verification = load_json(verification_path)

    require(admission.get("status") == "ADMITTED", "rollback not admitted")
    require(
        admission.get("authorization_only") is True,
        "rollback admission must be authorization-only",
    )
    require(admission.get("rollback_deployed") is False, "admission cannot prove rollback")
    require(
        admission.get("database_strategy") == "KEEP_FORWARD_SCHEMA",
        "rollback database strategy invalid",
    )
    require(
        admission.get("database_downgrade_authorized") is False,
        "database downgrade must not be authorized",
    )

    require(verification.get("schema_version") == 1, "unsupported schema")
    require(verification.get("status") == "VERIFIED", "status must be VERIFIED")
    require(
        verification.get("verification_scope") == "HOSTED_PRODUCTION_ROLLBACK",
        "verification_scope invalid",
    )
    require(verification.get("rollback_deployed") is True, "rollback deployment not proven")
    require(
        verification.get("runtime_identity_verified") is True,
        "rollback runtime identity not verified",
    )
    require(
        verification.get("database_schema_preserved") is True,
        "Production schema preservation not verified",
    )
    require(
        verification.get("database_downgrade_performed") is False,
        "database downgrade must not occur",
    )

    current_commit = verification.get("rolled_back_from_commit_sha")
    target_commit = verification.get("commit_sha")
    for value, field in (
        (current_commit, "rolled_back_from_commit_sha"),
        (target_commit, "commit_sha"),
    ):
        require(
            isinstance(value, str) and COMMIT_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )
    require(
        current_commit == admission.get("current_commit_sha"),
        "rolled-back-from commit mismatch",
    )
    require(target_commit == admission.get("target_commit_sha"), "target commit mismatch")

    expected_deployment = admission.get("expected_rollback_deployment_id")
    require(
        isinstance(expected_deployment, str)
        and DEPLOYMENT_ID_RE.fullmatch(expected_deployment) is not None,
        "expected rollback deployment invalid",
    )
    require(
        verification.get("deployment_id") == expected_deployment,
        "verified deployment id mismatch",
    )
    require(
        verification.get("production_target") == admission.get("production_target"),
        "production target mismatch",
    )
    require(
        verification.get("production_endpoint") == admission.get("production_endpoint"),
        "production endpoint mismatch",
    )
    require(
        verification.get("production_rollback_admission_run_id")
        == admission.get("production_rollback_admission_run_id"),
        "rollback admission run mismatch",
    )

    require(backend.get("status") == "ready", "backend release health not ready")
    require(
        str(backend.get("environment", "")).lower() in {"prod", "production"},
        "backend environment is not Production",
    )
    require(backend.get("git_commit") == target_commit, "backend target commit mismatch")
    require(
        backend.get("image_id") == admission.get("target_backend_image_id"),
        "backend target image mismatch",
    )
    require(
        backend.get("deployment_id") == expected_deployment,
        "backend rollback deployment mismatch",
    )

    migrations = backend.get("database_migration_versions")
    require(
        migrations == admission.get("pre_rollback_database_migration_versions"),
        "database migration identity changed during rollback",
    )

    require(frontend.get("git_commit") == target_commit, "frontend target commit mismatch")
    require(
        frontend.get("image_id") == admission.get("target_frontend_image_id"),
        "frontend target image mismatch",
    )
    require(
        frontend.get("deployment_id") == expected_deployment,
        "frontend rollback deployment mismatch",
    )
    require(
        frontend.get("application_version") == backend.get("application_version"),
        "application version mismatch",
    )

    for field in ("backend_image_id", "frontend_image_id"):
        value = verification.get(field)
        require(
            isinstance(value, str) and IMAGE_ID_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )
    require(
        verification.get("backend_image_id") == backend.get("image_id"),
        "verified backend image mismatch",
    )
    require(
        verification.get("frontend_image_id") == frontend.get("image_id"),
        "verified frontend image mismatch",
    )
    require(
        verification.get("database_migration_versions") == migrations,
        "verified migration identity mismatch",
    )

    for field, path in (
        ("rollback_admission_sha256", admission_path),
        ("backend_release_observation_sha256", backend_path),
        ("frontend_release_observation_sha256", frontend_path),
    ):
        value = verification.get(field)
        require(
            isinstance(value, str) and SHA256_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )
        require(value == digest(path), f"{field} mismatch")

    verification_run_id = verification.get("production_rollback_verification_run_id")
    require(
        isinstance(verification_run_id, str) and verification_run_id.isdigit(),
        "production_rollback_verification_run_id invalid",
    )
    verifier = verification.get("verifier")
    require(
        isinstance(verifier, str) and verifier and not verifier.endswith("[bot]"),
        "verifier must be a human GitHub actor",
    )
    parse_timestamp(verification.get("verified_at"), "verified_at")

    print(
        json.dumps(
            {
                "status": "valid",
                "rolled_back_from_commit_sha": current_commit,
                "commit_sha": target_commit,
                "deployment_id": expected_deployment,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
