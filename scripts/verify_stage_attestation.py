#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"stage attestation invalid: {message}")


def load_json(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"stage attestation invalid: cannot parse {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def main() -> None:
    require(
        len(sys.argv) == 3,
        "usage: verify_stage_attestation.py <release-dir> <attestation-file>",
    )
    release_dir = Path(sys.argv[1]).resolve()
    attestation_path = Path(sys.argv[2]).resolve()

    manifest_path = release_dir / "manifest.json"
    manifest = load_json(manifest_path)
    attestation = load_json(attestation_path)

    require(attestation.get("schema_version") == 1, "unsupported schema")
    require(attestation.get("status") == "PASSED", "status must be PASSED")
    require(
        attestation.get("environment_class") == "STAGE_ADMISSION",
        "environment_class invalid",
    )
    require(attestation.get("hosted_stage") is False, "hosted_stage must be false")

    commit_sha = attestation.get("commit_sha")
    source_ci_run_id = attestation.get("source_ci_run_id")
    stage_run_id = attestation.get("stage_admission_run_id")
    manifest_sha256 = attestation.get("release_manifest_sha256")
    backend_image_id = attestation.get("backend_image_id")
    frontend_image_id = attestation.get("frontend_image_id")

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
        isinstance(manifest_sha256, str)
        and SHA256_RE.fullmatch(manifest_sha256) is not None,
        "release_manifest_sha256 invalid",
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

    require(manifest.get("commit_sha") == commit_sha, "commit mismatch")
    require(manifest.get("workflow_run_id") == source_ci_run_id, "source run mismatch")
    require(
        hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        == manifest_sha256,
        "release manifest SHA-256 mismatch",
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

    print(
        json.dumps(
            {
                "status": "valid",
                "commit_sha": commit_sha,
                "source_ci_run_id": source_ci_run_id,
                "stage_admission_run_id": stage_run_id,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
