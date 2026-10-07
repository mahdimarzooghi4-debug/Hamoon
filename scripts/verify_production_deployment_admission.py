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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"production deployment admission invalid: {message}")


def load_json(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"production deployment admission invalid: cannot parse {path}: {exc}"
        ) from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def production_endpoint_valid(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
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
        or address.is_unspecified
        or address.is_private
        or address.is_link_local
    )


def main() -> None:
    require(
        len(sys.argv) == 6,
        (
            "usage: verify_production_deployment_admission.py "
            "<release-dir> <stage-attestation> <release-approval> "
            "<operational-readiness> <admission>"
        ),
    )

    release_dir = Path(sys.argv[1]).resolve()
    stage_path = Path(sys.argv[2]).resolve()
    approval_path = Path(sys.argv[3]).resolve()
    readiness_path = Path(sys.argv[4]).resolve()
    admission_path = Path(sys.argv[5]).resolve()
    manifest_path = release_dir / "manifest.json"

    manifest = load_json(manifest_path)
    stage = load_json(stage_path)
    approval = load_json(approval_path)
    readiness = load_json(readiness_path)
    admission = load_json(admission_path)

    require(admission.get("schema_version") == 1, "unsupported schema")
    require(admission.get("status") == "ADMITTED", "status must be ADMITTED")
    require(
        admission.get("admission_scope") == "PRODUCTION_DEPLOYMENT",
        "admission_scope invalid",
    )
    require(
        admission.get("production_deployed") is False,
        "admission must not claim deployment occurred",
    )

    require(stage.get("status") == "PASSED", "Stage admission did not pass")
    require(
        approval.get("status") == "APPROVED",
        "Release Approval is not APPROVED",
    )
    require(
        approval.get("approval_scope") == "RELEASE_TO_PRODUCTION",
        "Release Approval scope invalid",
    )
    require(
        approval.get("authorization_only") is True,
        "Release Approval must be authorization-only",
    )
    require(
        approval.get("production_deployed") is False,
        "Release Approval must not claim deployment",
    )
    require(readiness.get("schema_version") == 1, "readiness schema invalid")
    require(readiness.get("status") == "READY", "operational readiness is not READY")
    require(
        readiness.get("readiness_scope") == "PRODUCTION_EXTERNAL_INTEGRATIONS",
        "operational readiness scope invalid",
    )
    require(
        readiness.get("production_deployed") is False,
        "operational readiness must not claim deployment",
    )
    readiness_actor = readiness.get("actor")
    require(
        isinstance(readiness_actor, str)
        and readiness_actor
        and not readiness_actor.endswith("[bot]"),
        "operational readiness actor must be human",
    )
    readiness_checks = readiness.get("checks")
    require(
        isinstance(readiness_checks, dict)
        and bool(readiness_checks)
        and all(value is True for value in readiness_checks.values()),
        "operational readiness checks must all pass",
    )

    commit_sha = admission.get("commit_sha")
    source_ci_run_id = admission.get("source_ci_run_id")
    stage_run_id = admission.get("stage_admission_run_id")
    approval_run_id = admission.get("release_approval_run_id")
    readiness_run_id = admission.get("operational_readiness_run_id")
    admission_run_id = admission.get("deployment_admission_run_id")

    require(
        isinstance(commit_sha, str) and COMMIT_RE.fullmatch(commit_sha) is not None,
        "commit_sha invalid",
    )
    for value, label in (
        (source_ci_run_id, "source_ci_run_id"),
        (stage_run_id, "stage_admission_run_id"),
        (approval_run_id, "release_approval_run_id"),
        (readiness_run_id, "operational_readiness_run_id"),
        (admission_run_id, "deployment_admission_run_id"),
    ):
        require(
            isinstance(value, str) and value.isdigit(),
            f"{label} invalid",
        )

    for field in (
        "release_manifest_sha256",
        "stage_attestation_sha256",
        "release_approval_sha256",
        "operational_readiness_sha256",
    ):
        value = admission.get(field)
        require(
            isinstance(value, str) and SHA256_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )

    backend_image_id = admission.get("backend_image_id")
    frontend_image_id = admission.get("frontend_image_id")
    for value, label in (
        (backend_image_id, "backend_image_id"),
        (frontend_image_id, "frontend_image_id"),
    ):
        require(
            isinstance(value, str) and IMAGE_ID_RE.fullmatch(value) is not None,
            f"{label} invalid",
        )

    deployer = admission.get("deployer")
    require(
        isinstance(deployer, str)
        and deployer
        and not deployer.endswith("[bot]"),
        "deployer must be a human GitHub actor",
    )
    production_target = admission.get("production_target")
    require(
        isinstance(production_target, str) and production_target.strip(),
        "production_target missing",
    )
    expected_deployment_id = admission.get("expected_deployment_id")
    require(
        isinstance(expected_deployment_id, str)
        and re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", expected_deployment_id)
        is not None,
        "expected_deployment_id invalid",
    )
    require(
        production_endpoint_valid(admission.get("production_endpoint")),
        "production_endpoint must be a non-local HTTPS endpoint",
    )

    admitted_at = admission.get("admitted_at")
    require(isinstance(admitted_at, str), "admitted_at missing")
    try:
        timestamp = datetime.fromisoformat(admitted_at)
    except ValueError as exc:
        raise SystemExit(
            "production deployment admission invalid: admitted_at invalid"
        ) from exc
    require(timestamp.tzinfo is not None, "admitted_at must include timezone")

    require(manifest.get("commit_sha") == commit_sha, "manifest commit mismatch")
    require(
        manifest.get("workflow_run_id") == source_ci_run_id,
        "source CI run mismatch",
    )
    require(stage.get("commit_sha") == commit_sha, "Stage commit mismatch")
    require(
        stage.get("source_ci_run_id") == source_ci_run_id,
        "Stage source CI run mismatch",
    )
    require(
        stage.get("stage_admission_run_id") == stage_run_id,
        "Stage run mismatch",
    )
    require(approval.get("commit_sha") == commit_sha, "approval commit mismatch")
    require(
        approval.get("source_ci_run_id") == source_ci_run_id,
        "approval source CI run mismatch",
    )
    require(
        approval.get("stage_admission_run_id") == stage_run_id,
        "approval Stage run mismatch",
    )
    require(
        approval.get("approval_run_id") == approval_run_id,
        "approval run mismatch",
    )
    require(readiness.get("commit_sha") == commit_sha, "readiness commit mismatch")
    require(
        readiness.get("workflow_run_id") == readiness_run_id,
        "operational readiness run mismatch",
    )
    require(
        admission.get("operational_readiness_status") == "READY",
        "operational_readiness_status invalid",
    )

    readiness_checked_at = readiness.get("checked_at")
    require(isinstance(readiness_checked_at, str), "readiness checked_at missing")
    try:
        readiness_timestamp = datetime.fromisoformat(readiness_checked_at)
    except ValueError as exc:
        raise SystemExit(
            "production deployment admission invalid: readiness checked_at invalid"
        ) from exc
    require(
        readiness_timestamp.tzinfo is not None,
        "readiness checked_at must include timezone",
    )

    require(
        file_sha256(manifest_path) == admission["release_manifest_sha256"],
        "release manifest SHA-256 mismatch",
    )
    require(
        file_sha256(stage_path) == admission["stage_attestation_sha256"],
        "Stage attestation SHA-256 mismatch",
    )
    require(
        file_sha256(approval_path) == admission["release_approval_sha256"],
        "Release Approval SHA-256 mismatch",
    )
    require(
        file_sha256(readiness_path) == admission["operational_readiness_sha256"],
        "Operational Readiness SHA-256 mismatch",
    )

    backend = manifest.get("backend")
    frontend = manifest.get("frontend")
    require(isinstance(backend, dict), "backend manifest missing")
    require(isinstance(frontend, dict), "frontend manifest missing")
    require(
        backend.get("image_id") == backend_image_id,
        "backend image identity mismatch",
    )
    require(
        frontend.get("image_id") == frontend_image_id,
        "frontend image identity mismatch",
    )
    require(
        approval.get("backend_image_id") == backend_image_id,
        "approval backend image mismatch",
    )
    require(
        approval.get("frontend_image_id") == frontend_image_id,
        "approval frontend image mismatch",
    )
    require(
        admission.get("release_approver") == approval.get("approver"),
        "release approver mismatch",
    )
    require(
        admission.get("change_reference") == approval.get("change_reference"),
        "change reference mismatch",
    )
    require(
        admission.get("stage_status") == "PASSED",
        "stage_status invalid",
    )
    require(
        admission.get("release_approval_status") == "APPROVED",
        "release_approval_status invalid",
    )

    print(
        json.dumps(
            {
                "status": "valid",
                "commit_sha": commit_sha,
                "deployer": deployer,
                "production_target": production_target,
                "production_endpoint": admission.get("production_endpoint"),
                "expected_deployment_id": expected_deployment_id,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
