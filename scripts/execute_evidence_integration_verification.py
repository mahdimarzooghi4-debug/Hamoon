#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from hamoon.app.config.settings import Settings
from hamoon.infrastructure.evidence_verification import (
    EvidenceIntegrationVerificationError,
    verify_evidence_integration,
)


async def _run(output_dir: Path) -> None:
    settings = Settings(_env_file=None, environment="local")
    scanner_token = (
        settings.evidence_scanner_token.get_secret_value()
        if settings.evidence_scanner_token is not None
        else ""
    )

    try:
        observation = await verify_evidence_integration(
            commit_sha=settings.git_commit.strip(),
            s3_endpoint=settings.evidence_s3_endpoint,
            s3_access_key=settings.evidence_s3_access_key,
            s3_secret_key=settings.evidence_s3_secret_key,
            s3_bucket=settings.evidence_s3_bucket,
            s3_region=settings.evidence_s3_region,
            scanner_endpoint=settings.evidence_scanner_endpoint or "",
            scanner_token=scanner_token,
            storage_timeout_seconds=settings.evidence_s3_request_timeout_seconds,
            scanner_timeout_seconds=settings.evidence_scanner_timeout_seconds,
        )
    except EvidenceIntegrationVerificationError as exc:
        raise SystemExit(f"evidence integration verification failed: {exc}") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "evidence-integration-observation.json").write_text(
        json.dumps(observation, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: execute_evidence_integration_verification.py <output-dir>"
        )
    asyncio.run(_run(Path(sys.argv[1])))


if __name__ == "__main__":
    main()
