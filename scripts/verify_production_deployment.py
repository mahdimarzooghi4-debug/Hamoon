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
        raise SystemExit(f"production deployment invalid: {message}")


def load_json(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing file {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise SystemExit(
            f"production deployment invalid: invalid JSON in {path}"
        ) from exc
    require(isinstance(payload, dict), f"{path} must contain an object")
    return payload


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_timestamp(value: object, field: str) -> None:
    require(isinstance(value, str), f"{field} missing")
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(
            f"production deployment invalid: {field} invalid"
        ) from exc
    require(timestamp.tzinfo is not None, f"{field} must include timezone")


def main() -> None:
    if len(sys.argv) != 6:
        raise SystemExit(
            "usage: verify_production_deployment.py "
            "<release-dir> <deployment-admission.json> "
            "<orchestrator-request.json> <orchestrator-receipt.json> "
            "<production-deployment.json>"
        )

    release_dir = Path(sys.argv[1])
    admission_path = Path(sys.argv[2])
    request_path = Path(sys.argv[3])
    receipt_path = Path(sys.argv[4])
    deployment_path = Path(sys.argv[5])

    manifest_path = release_dir / "manifest.json"
    manifest = load_json(manifest_path)
    admission = load_json(admission_path)
    request = load_json(request_path)
    receipt = load_json(receipt_path)
    deployment = load_json(deployment_path)

    require(deployment.get("schema_version") == 1, "unsupported schema_version")
    require(deployment.get("status") == "DEPLOYED", "status must be DEPLOYED")
    require(
        deployment.get("deployment_scope") == "HOSTED_PRODUCTION_EXECUTION",
        "deployment_scope invalid",
    )
    require(deployment.get("production_deployed") is True, "production_deployed must be true")

    commit_sha = deployment.get("commit_sha")
    require(
        isinstance(commit_sha, str) and COMMIT_RE.fullmatch(commit_sha) is not None,
        "commit_sha invalid",
    )
    require(commit_sha == admission.get("commit_sha"), "commit mismatch with admission")
    require(commit_sha == manifest.get("commit_sha"), "commit mismatch with release")

    backend = manifest.get("backend")
    frontend = manifest.get("frontend")
    require(isinstance(backend, dict), "release backend metadata missing")
    require(isinstance(frontend, dict), "release frontend metadata missing")

    for field in (
        "source_ci_run_id",
        "stage_admission_run_id",
        "release_approval_run_id",
        "deployment_admission_run_id",
    ):
        value = deployment.get(field)
        require(isinstance(value, str) and value.isdigit(), f"{field} invalid")
        require(value == admission.get(field), f"{field} mismatch")

    production_deployment_run_id = deployment.get("production_deployment_run_id")
    require(
        isinstance(production_deployment_run_id, str)
        and production_deployment_run_id.isdigit(),
        "production_deployment_run_id invalid",
    )

    expected_pairs = (
        ("production_target", admission.get("production_target")),
        ("production_endpoint", admission.get("production_endpoint")),
        ("deployment_id", admission.get("expected_deployment_id")),
        ("backend_image_id", admission.get("backend_image_id")),
        ("frontend_image_id", admission.get("frontend_image_id")),
    )
    for field, expected in expected_pairs:
        require(deployment.get(field) == expected, f"{field} mismatch")

    for field in ("backend_image_id", "frontend_image_id"):
        value = deployment.get(field)
        require(
            isinstance(value, str) and IMAGE_ID_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )

    require(
        deployment.get("backend_image_id") == backend.get("image_id"),
        "backend image mismatch with release",
    )
    require(
        deployment.get("frontend_image_id") == frontend.get("image_id"),
        "frontend image mismatch with release",
    )

    hash_bindings = (
        ("release_manifest_sha256", manifest_path),
        ("deployment_admission_sha256", admission_path),
        ("orchestrator_request_sha256", request_path),
        ("orchestrator_receipt_sha256", receipt_path),
    )
    for field, path in hash_bindings:
        value = deployment.get(field)
        require(
            isinstance(value, str) and SHA256_RE.fullmatch(value) is not None,
            f"{field} invalid",
        )
        require(file_sha256(path) == value, f"{field} mismatch")

    require(request.get("operation") == "DEPLOY_HAMOON_RELEASE", "request operation invalid")
    require(request.get("commit_sha") == commit_sha, "request commit mismatch")
    require(
        request.get("source_ci_run_id") == deployment.get("source_ci_run_id"),
        "request source CI mismatch",
    )
    require(
        request.get("production_target") == deployment.get("production_target"),
        "request production target mismatch",
    )
    require(
        request.get("production_endpoint") == deployment.get("production_endpoint"),
        "request production endpoint mismatch",
    )
    require(
        request.get("deployment_id") == deployment.get("deployment_id"),
        "request deployment id mismatch",
    )
    request_backend = request.get("backend")
    request_frontend = request.get("frontend")
    request_governance = request.get("governance")
    require(isinstance(request_backend, dict), "request backend metadata missing")
    require(isinstance(request_frontend, dict), "request frontend metadata missing")
    require(isinstance(request_governance, dict), "request governance metadata missing")
    require(
        request_backend.get("image_id") == deployment.get("backend_image_id"),
        "request backend image mismatch",
    )
    require(
        request_frontend.get("image_id") == deployment.get("frontend_image_id"),
        "request frontend image mismatch",
    )
    require(
        request.get("release_artifact_name") == f"hamoon-release-{commit_sha}",
        "request release artifact mismatch",
    )
    require(
        request_governance.get("release_approval_run_id")
        == admission.get("release_approval_run_id"),
        "request release approval run mismatch",
    )
    require(
        request_governance.get("deployment_admission_run_id")
        == admission.get("deployment_admission_run_id"),
        "request deployment admission run mismatch",
    )
    require(
        request_governance.get("release_manifest_sha256")
        == admission.get("release_manifest_sha256"),
        "request release manifest hash mismatch",
    )
    require(
        request_governance.get("release_approval_sha256")
        == admission.get("release_approval_sha256"),
        "request release approval hash mismatch",
    )

    require(receipt.get("status") == "DEPLOYED", "receipt status must be DEPLOYED")
    for field in (
        "commit_sha",
        "deployment_id",
        "production_target",
        "production_endpoint",
        "backend_image_id",
        "frontend_image_id",
    ):
        require(
            receipt.get(field) == deployment.get(field),
            f"receipt {field} mismatch",
        )

    receipt_id = deployment.get("receipt_id")
    require(isinstance(receipt_id, str) and receipt_id, "receipt_id missing")
    require(receipt_id == receipt.get("receipt_id"), "receipt_id mismatch")
    require(len(receipt_id) <= 200, "receipt_id too long")

    deployer = deployment.get("deployer")
    require(isinstance(deployer, str) and deployer, "deployer missing")
    require(not deployer.endswith("[bot]"), "deployer must be a human GitHub actor")
    _require_timestamp(deployment.get("deployed_at"), "deployed_at")
    _require_timestamp(deployment.get("attested_at"), "attested_at")
    require(
        deployment.get("deployed_at") == receipt.get("deployed_at"),
        "deployed_at mismatch with receipt",
    )

    print(
        json.dumps(
            {
                "status": "valid",
                "commit_sha": commit_sha,
                "deployment_id": deployment.get("deployment_id"),
                "production_endpoint": deployment.get("production_endpoint"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
