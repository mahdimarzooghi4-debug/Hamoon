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
        raise SystemExit(f"production verification invalid: {message}")


def load_json(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"production verification invalid: cannot parse {path}: {exc}"
        ) from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    require(
        len(sys.argv) == 5,
        (
            "usage: verify_production_verification.py "
            "<deployment-admission> <backend-release> "
            "<frontend-release> <verification>"
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

    require(admission.get("status") == "ADMITTED", "deployment not admitted")
    require(
        admission.get("production_deployed") is False,
        "admission must precede deployment evidence",
    )
    require(verification.get("schema_version") == 1, "unsupported schema")
    require(verification.get("status") == "VERIFIED", "status must be VERIFIED")
    require(
        verification.get("verification_scope") == "HOSTED_PRODUCTION_RUNTIME",
        "verification_scope invalid",
    )
    require(
        verification.get("production_deployed") is True,
        "verification must prove Production deployment",
    )
    require(
        verification.get("runtime_identity_verified") is True,
        "runtime identity must be verified",
    )

    commit_sha = verification.get("commit_sha")
    require(
        isinstance(commit_sha, str) and COMMIT_RE.fullmatch(commit_sha) is not None,
        "commit_sha invalid",
    )
    require(admission.get("commit_sha") == commit_sha, "commit mismatch")

    for field in (
        "source_ci_run_id",
        "stage_admission_run_id",
        "release_approval_run_id",
        "deployment_admission_run_id",
    ):
        require(
            verification.get(field) == admission.get(field),
            f"{field} mismatch",
        )

    verification_run_id = verification.get("production_verification_run_id")
    require(
        isinstance(verification_run_id, str) and verification_run_id.isdigit(),
        "production_verification_run_id invalid",
    )

    require(
        verification.get("production_target") == admission.get("production_target"),
        "production_target mismatch",
    )
    require(
        verification.get("production_endpoint")
        == admission.get("production_endpoint"),
        "production_endpoint mismatch",
    )

    expected_deployment_id = admission.get("expected_deployment_id")
    require(
        isinstance(expected_deployment_id, str)
        and DEPLOYMENT_ID_RE.fullmatch(expected_deployment_id) is not None,
        "expected_deployment_id invalid",
    )
    require(
        verification.get("deployment_id") == expected_deployment_id,
        "deployment_id mismatch",
    )

    require(backend.get("status") == "ready", "backend release health not ready")
    require(
        str(backend.get("environment", "")).lower() in {"prod", "production"},
        "backend environment is not Production",
    )
    require(backend.get("git_commit") == commit_sha, "backend commit mismatch")
    require(
        backend.get("image_id") == admission.get("backend_image_id"),
        "backend image mismatch",
    )
    require(
        backend.get("deployment_id") == expected_deployment_id,
        "backend deployment_id mismatch",
    )
    migrations = backend.get("database_migration_versions")
    require(
        isinstance(migrations, list)
        and len(migrations) > 0
        and all(isinstance(value, str) and value for value in migrations),
        "database migration identity missing",
    )

    require(frontend.get("git_commit") == commit_sha, "frontend commit mismatch")
    require(
        frontend.get("image_id") == admission.get("frontend_image_id"),
        "frontend image mismatch",
    )
    require(
        frontend.get("deployment_id") == expected_deployment_id,
        "frontend deployment_id mismatch",
    )
    require(
        frontend.get("application_version") == backend.get("application_version"),
        "application version mismatch",
    )

    for field, path in (
        ("deployment_admission_sha256", admission_path),
        ("backend_release_observation_sha256", backend_path),
        ("frontend_release_observation_sha256", frontend_path),
    ):
        value = verification.get(field)
        require(
            isinstance(value, str) and SHA256_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )
        require(file_sha256(path) == value, f"{field} mismatch")

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
        verification.get("application_version") == backend.get("application_version"),
        "verified application version mismatch",
    )
    require(
        verification.get("database_migration_versions") == migrations,
        "verified migration identity mismatch",
    )

    verifier = verification.get("verifier")
    require(
        isinstance(verifier, str) and verifier,
        "verifier missing",
    )
    verified_at = verification.get("verified_at")
    require(isinstance(verified_at, str), "verified_at missing")
    try:
        timestamp = datetime.fromisoformat(verified_at)
    except ValueError as exc:
        raise SystemExit(
            "production verification invalid: verified_at invalid"
        ) from exc
    require(timestamp.tzinfo is not None, "verified_at must include timezone")

    print(
        json.dumps(
            {
                "status": "valid",
                "commit_sha": commit_sha,
                "deployment_id": expected_deployment_id,
                "production_endpoint": admission.get("production_endpoint"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
