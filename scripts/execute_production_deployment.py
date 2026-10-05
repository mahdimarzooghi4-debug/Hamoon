#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from hamoon.deployment.orchestrator import (
    DeploymentOrchestratorError,
    execute_production_deployment,
    execute_production_preflight,
)


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"production deployment failed: cannot read {path}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(
            f"production deployment failed: {path} must contain a JSON object"
        )
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit(
            "usage: execute_production_deployment.py "
            "<release-dir> <deployment-admission.json> "
            "<runtime-preflight.json> <output-dir>"
        )

    release_dir = Path(sys.argv[1])
    admission_path = Path(sys.argv[2])
    requirements_path = Path(sys.argv[3])
    output_dir = Path(sys.argv[4])
    manifest_path = release_dir / "manifest.json"

    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    endpoint = os.environ.get("HAMOON_DEPLOY_ORCHESTRATOR_ENDPOINT", "").strip()
    token = os.environ.get("HAMOON_DEPLOY_ORCHESTRATOR_TOKEN", "")

    if not repository:
        raise SystemExit("production deployment failed: GITHUB_REPOSITORY is required")
    if not endpoint:
        raise SystemExit(
            "production deployment failed: HAMOON_DEPLOY_ORCHESTRATOR_ENDPOINT is required"
        )
    if not token:
        raise SystemExit(
            "production deployment failed: HAMOON_DEPLOY_ORCHESTRATOR_TOKEN is required"
        )

    manifest = _load_json(manifest_path)
    admission = _load_json(admission_path)
    requirements = _load_json(requirements_path)
    requirements_sha256 = _sha256(requirements_path)

    try:
        preflight_request, preflight_receipt = execute_production_preflight(
            orchestrator_endpoint=endpoint,
            token=token,
            repository=repository,
            manifest=manifest,
            admission=admission,
            requirements=requirements,
            requirements_sha256=requirements_sha256,
        )
        deployment_request, deployment_receipt = execute_production_deployment(
            orchestrator_endpoint=endpoint,
            token=token,
            repository=repository,
            manifest=manifest,
            admission=admission,
        )
    except DeploymentOrchestratorError as exc:
        raise SystemExit(f"production deployment failed: {exc}") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in (
        ("preflight-request.json", preflight_request),
        ("preflight-receipt.json", preflight_receipt),
        ("orchestrator-request.json", deployment_request),
        ("orchestrator-receipt.json", deployment_receipt),
    ):
        (output_dir / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
