#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from hamoon.deployment.orchestrator import (
    DeploymentOrchestratorError,
    execute_production_deployment,
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


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: execute_production_deployment.py "
            "<release-dir> <deployment-admission.json> <output-dir>"
        )

    release_dir = Path(sys.argv[1])
    admission_path = Path(sys.argv[2])
    output_dir = Path(sys.argv[3])
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

    try:
        request_payload, receipt = execute_production_deployment(
            orchestrator_endpoint=endpoint,
            token=token,
            repository=repository,
            manifest=_load_json(manifest_path),
            admission=_load_json(admission_path),
        )
    except DeploymentOrchestratorError as exc:
        raise SystemExit(f"production deployment failed: {exc}") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "orchestrator-request.json").write_text(
        json.dumps(request_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "orchestrator-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
