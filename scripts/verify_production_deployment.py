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


def _checkpoint_contract(requirements: dict[str, object]) -> dict[str, object]:
    raw = requirements.get("internal_model_checkpoint")
    require(isinstance(raw, dict), "internal model checkpoint contract missing")
    checkpoint = dict(raw)
    required_fields = {
        "model_id",
        "revision",
        "model_sha256",
        "tokenizer_sha256",
        "execution_mode",
        "network_model_download",
    }
    require(set(checkpoint) == required_fields, "internal model checkpoint fields invalid")
    for field in ("model_id", "revision", "model_sha256", "tokenizer_sha256", "execution_mode"):
        value = checkpoint.get(field)
        require(isinstance(value, str) and bool(value.strip()), f"checkpoint {field} invalid")
    for field in ("model_sha256", "tokenizer_sha256"):
        value = checkpoint.get(field)
        require(
            isinstance(value, str) and SHA256_RE.fullmatch(value) is not None,
            f"checkpoint {field} invalid",
        )
    require(checkpoint.get("execution_mode") == "IN_PROCESS", "checkpoint execution_mode invalid")
    require(
        checkpoint.get("network_model_download") is False,
        "checkpoint network model download must be disabled",
    )
    return checkpoint


def _required_checks(requirements: dict[str, object]) -> list[str]:
    require(requirements.get("schema_version") == 2, "preflight schema invalid")
    require(
        requirements.get("contract") == "HAMOON_PRODUCTION_RUNTIME_PREFLIGHT",
        "preflight contract invalid",
    )
    raw = requirements.get("required_checks")
    require(isinstance(raw, list) and bool(raw), "preflight required_checks missing")
    checks: list[str] = []
    for value in raw:
        require(isinstance(value, str) and bool(value.strip()), "preflight check invalid")
        check = value.strip()
        require(check not in checks, "preflight checks must be unique")
        checks.append(check)
    return checks


def main() -> None:
    if len(sys.argv) != 9:
        raise SystemExit(
            "usage: verify_production_deployment.py "
            "<release-dir> <deployment-admission.json> <runtime-preflight.json> "
            "<preflight-request.json> <preflight-receipt.json> "
            "<orchestrator-request.json> <orchestrator-receipt.json> "
            "<production-deployment.json>"
        )

    release_dir = Path(sys.argv[1])
    admission_path = Path(sys.argv[2])
    requirements_path = Path(sys.argv[3])
    preflight_request_path = Path(sys.argv[4])
    preflight_receipt_path = Path(sys.argv[5])
    request_path = Path(sys.argv[6])
    receipt_path = Path(sys.argv[7])
    deployment_path = Path(sys.argv[8])

    manifest_path = release_dir / "manifest.json"
    manifest = load_json(manifest_path)
    admission = load_json(admission_path)
    requirements = load_json(requirements_path)
    preflight_request = load_json(preflight_request_path)
    preflight_receipt = load_json(preflight_receipt_path)
    request = load_json(request_path)
    receipt = load_json(receipt_path)
    deployment = load_json(deployment_path)
    required_checks = _required_checks(requirements)
    checkpoint_contract = _checkpoint_contract(requirements)

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
        ("runtime_preflight_contract_sha256", requirements_path),
        ("preflight_request_sha256", preflight_request_path),
        ("preflight_receipt_sha256", preflight_receipt_path),
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

    require(
        preflight_request.get("operation") == "PREFLIGHT_HAMOON_PRODUCTION",
        "preflight request operation invalid",
    )
    for field in (
        "commit_sha",
        "source_ci_run_id",
        "production_target",
        "production_endpoint",
        "deployment_id",
    ):
        require(
            preflight_request.get(field) == deployment.get(field),
            f"preflight request {field} mismatch",
        )
    preflight_meta = preflight_request.get("runtime_preflight")
    require(isinstance(preflight_meta, dict), "preflight request metadata missing")
    require(
        preflight_meta.get("contract_sha256") == file_sha256(requirements_path),
        "preflight contract hash mismatch",
    )
    require(
        preflight_meta.get("required_checks") == required_checks,
        "preflight required check set mismatch",
    )
    require(
        preflight_meta.get("internal_model_checkpoint") == checkpoint_contract,
        "preflight checkpoint contract mismatch",
    )

    require(preflight_receipt.get("status") == "READY", "preflight status must be READY")
    for field in (
        "commit_sha",
        "deployment_id",
        "production_target",
        "production_endpoint",
        "backend_image_id",
        "frontend_image_id",
    ):
        require(
            preflight_receipt.get(field) == deployment.get(field),
            f"preflight receipt {field} mismatch",
        )
    require(
        preflight_receipt.get("internal_model_checkpoint") == checkpoint_contract,
        "preflight checkpoint attestation mismatch",
    )
    checks = preflight_receipt.get("checks")
    require(isinstance(checks, dict), "preflight receipt checks missing")
    require(set(checks) == set(required_checks), "preflight receipt check set mismatch")
    for check in required_checks:
        require(checks.get(check) is True, f"preflight required check failed: {check}")
    preflight_id = deployment.get("preflight_id")
    require(isinstance(preflight_id, str) and bool(preflight_id), "preflight_id missing")
    require(preflight_id == preflight_receipt.get("preflight_id"), "preflight_id mismatch")
    _require_timestamp(preflight_receipt.get("checked_at"), "preflight checked_at")

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
    request_preflight = request.get("runtime_preflight")
    require(isinstance(request_backend, dict), "request backend metadata missing")
    require(isinstance(request_frontend, dict), "request frontend metadata missing")
    require(isinstance(request_governance, dict), "request governance metadata missing")
    require(isinstance(request_preflight, dict), "request runtime preflight binding missing")
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
    require(
        request_preflight.get("preflight_id") == preflight_id,
        "request preflight_id mismatch",
    )
    require(
        request_preflight.get("contract_sha256") == file_sha256(requirements_path),
        "request preflight contract hash mismatch",
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

    require(
        receipt.get("preflight_id") == preflight_id,
        "receipt preflight_id mismatch",
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
                "preflight_id": preflight_id,
                "production_endpoint": deployment.get("production_endpoint"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
