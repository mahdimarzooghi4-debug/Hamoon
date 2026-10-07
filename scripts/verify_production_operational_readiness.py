#!/usr/bin/env python3
from __future__ import annotations

import ipaddress
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")

REQUIRED_VALUES = (
    "HAMOON_DEPLOY_ORCHESTRATOR_ENDPOINT",
    "HAMOON_DEPLOY_ORCHESTRATOR_TOKEN",
    "HAMOON_PRODUCTION_METRICS_TOKEN",
    "HAMOON_OBSERVABILITY_VERIFICATION_URL",
    "HAMOON_OBSERVABILITY_VERIFICATION_TOKEN",
    "HAMOON_ALERTMANAGER_URL",
    "HAMOON_ALERTMANAGER_METRICS_URL",
    "HAMOON_ALERTMANAGER_BEARER_TOKEN",
    "HAMOON_EVIDENCE_S3_ENDPOINT",
    "HAMOON_EVIDENCE_S3_ACCESS_KEY",
    "HAMOON_EVIDENCE_S3_SECRET_KEY",
    "HAMOON_EVIDENCE_S3_BUCKET",
    "HAMOON_EVIDENCE_S3_REGION",
    "HAMOON_EVIDENCE_SCANNER_ENDPOINT",
    "HAMOON_EVIDENCE_SCANNER_TOKEN",
    "HAMOON_PROVIDER_DISPATCH_CONFIG",
    "HAMOON_RECOVERY_VERIFICATION_URL",
    "HAMOON_RECOVERY_VERIFICATION_TOKEN",
)

REMOTE_HTTPS_VALUES = (
    "HAMOON_DEPLOY_ORCHESTRATOR_ENDPOINT",
    "HAMOON_OBSERVABILITY_VERIFICATION_URL",
    "HAMOON_ALERTMANAGER_URL",
    "HAMOON_ALERTMANAGER_METRICS_URL",
    "HAMOON_EVIDENCE_S3_ENDPOINT",
    "HAMOON_EVIDENCE_SCANNER_ENDPOINT",
    "HAMOON_RECOVERY_VERIFICATION_URL",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"production operational readiness invalid: {message}")


def remote_https(value: str) -> bool:
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
        len(sys.argv) == 2,
        "usage: verify_production_operational_readiness.py <output.json>",
    )
    commit_sha = os.environ.get("HAMOON_READINESS_COMMIT_SHA", "").strip()
    actor = os.environ.get("HAMOON_READINESS_ACTOR", "").strip()
    workflow_run_id = os.environ.get("HAMOON_READINESS_RUN_ID", "").strip()

    require(COMMIT_RE.fullmatch(commit_sha) is not None, "commit SHA invalid")
    require(bool(actor) and not actor.endswith("[bot]"), "actor must be human")
    require(workflow_run_id.isdigit(), "workflow run id invalid")

    missing = [name for name in REQUIRED_VALUES if not os.environ.get(name, "").strip()]
    require(not missing, "required Production inputs missing: " + ",".join(missing))

    invalid_https = [
        name
        for name in REMOTE_HTTPS_VALUES
        if not remote_https(os.environ[name])
    ]
    require(
        not invalid_https,
        "Production endpoints must be remote HTTPS: " + ",".join(invalid_https),
    )

    require(
        len(os.environ["HAMOON_DEPLOY_ORCHESTRATOR_TOKEN"].strip()) >= 32,
        "deployment orchestrator token invalid",
    )
    require(
        len(os.environ["HAMOON_PRODUCTION_METRICS_TOKEN"].strip()) >= 32,
        "Production metrics token invalid",
    )
    require(
        len(os.environ["HAMOON_EVIDENCE_SCANNER_TOKEN"].strip()) >= 32,
        "evidence scanner token invalid",
    )

    checks = {name: True for name in REQUIRED_VALUES}
    output = {
        "schema_version": 1,
        "status": "READY",
        "readiness_scope": "PRODUCTION_EXTERNAL_INTEGRATIONS",
        "production_deployed": False,
        "commit_sha": commit_sha,
        "workflow_run_id": workflow_run_id,
        "actor": actor,
        "checks": checks,
        "checked_at": datetime.now(UTC).isoformat(),
    }
    output_path = Path(sys.argv[1])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "ready", "commit_sha": commit_sha}, sort_keys=True))


if __name__ == "__main__":
    main()
