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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"release approval invalid: {message}")


def load_json(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"release approval invalid: cannot parse {path}: {exc}"
        ) from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    require(
        len(sys.argv) == 4,
        (
            "usage: verify_release_approval.py "
            "<release-dir> <stage-attestation> <release-approval>"
        ),
    )
    release_dir = Path(sys.argv[1]).resolve()
    stage_path = Path(sys.argv[2]).resolve()
    approval_path = Path(sys.argv[3]).resolve()

    manifest_path = release_dir / "manifest.json"
    manifest = load_json(manifest_path)
    stage = load_json(stage_path)
    approval = load_json(approval_path)

    require(approval.get("schema_version") == 1, "unsupported schema")
    require(approval.get("status") == "APPROVED", "status must be APPROVED")
    require(
        approval.get("approval_scope") == "RELEASE_TO_PRODUCTION",
        "approval_scope invalid",
    )
    require(
        approval.get("authorization_only") is True,
        "authorization_only must be true",
    )
    require(
        approval.get("production_deployed") is False,
        "approval must not claim production deployment",
    )
    require(stage.get("status") == "PASSED", "Stage admission did not pass")

    commit_sha = approval.get("commit_sha")
    source_ci_run_id = approval.get("source_ci_run_id")
    stage_run_id = approval.get("stage_admission_run_id")
    approval_run_id = approval.get("approval_run_id")
    release_manifest_sha256 = approval.get("release_manifest_sha256")
    stage_attestation_sha256 = approval.get("stage_attestation_sha256")
    backend_image_id = approval.get("backend_image_id")
    frontend_image_id = approval.get("frontend_image_id")
    approver = approval.get("approver")
    change_reference = approval.get("change_reference")
    approval_note = approval.get("approval_note")
    approved_at = approval.get("approved_at")

    require(
        isinstance(commit_sha, str) and COMMIT_RE.fullmatch(commit_sha) is not None,
        "commit_sha invalid",
    )
    require(
        isinstance(source_ci_run_id, str) and source_ci_run_id.isdigit(),
        "source_ci_run_id invalid",
    )
    require(
        isinstance(stage_run_id, str) and stage_run_id.isdigit(),
        "stage_admission_run_id invalid",
    )
    require(
        isinstance(approval_run_id, str) and approval_run_id.isdigit(),
        "approval_run_id invalid",
    )
    require(
        isinstance(release_manifest_sha256, str)
        and SHA256_RE.fullmatch(release_manifest_sha256) is not None,
        "release_manifest_sha256 invalid",
    )
    require(
        isinstance(stage_attestation_sha256, str)
        and SHA256_RE.fullmatch(stage_attestation_sha256) is not None,
        "stage_attestation_sha256 invalid",
    )
    require(
        isinstance(backend_image_id, str)
        and IMAGE_ID_RE.fullmatch(backend_image_id) is not None,
        "backend_image_id invalid",
    )
    require(
        isinstance(frontend_image_id, str)
        and IMAGE_ID_RE.fullmatch(frontend_image_id) is not None,
        "frontend_image_id invalid",
    )
    require(
        isinstance(approver, str)
        and approver
        and not approver.endswith("[bot]"),
        "approver must be a human GitHub actor",
    )
    require(
        isinstance(change_reference, str) and change_reference.strip(),
        "change_reference missing",
    )
    require(
        isinstance(approval_note, str) and approval_note.strip(),
        "approval_note missing",
    )
    require(isinstance(approved_at, str), "approved_at missing")
    try:
        timestamp = datetime.fromisoformat(approved_at)
    except ValueError as exc:
        raise SystemExit("release approval invalid: approved_at invalid") from exc
    require(timestamp.tzinfo is not None, "approved_at must include timezone")

    require(manifest.get("commit_sha") == commit_sha, "manifest commit mismatch")
    require(
        manifest.get("workflow_run_id") == source_ci_run_id,
        "manifest source CI run mismatch",
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
    require(
        file_sha256(manifest_path) == release_manifest_sha256,
        "release manifest SHA-256 mismatch",
    )
    require(
        file_sha256(stage_path) == stage_attestation_sha256,
        "Stage attestation SHA-256 mismatch",
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
    require(approval.get("stage_status") == "PASSED", "stage_status invalid")

    print(
        json.dumps(
            {
                "status": "valid",
                "commit_sha": commit_sha,
                "approver": approver,
                "approval_run_id": approval_run_id,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
