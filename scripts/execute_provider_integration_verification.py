#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

from hamoon.app.config.settings import Settings
from hamoon.infrastructure.provider_dispatch import (
    ProviderDispatchConfigurationError,
    load_provider_dispatch_targets,
)
from hamoon.infrastructure.provider_verification import (
    ProviderIntegrationVerificationError,
    verify_provider_integration,
)


async def _run(provider_id: UUID, output_dir: Path) -> None:
    settings = Settings(_env_file=None)
    try:
        targets = load_provider_dispatch_targets(settings)
    except ProviderDispatchConfigurationError as exc:
        raise SystemExit(f"provider verification failed: {exc}") from exc

    target = targets.get(provider_id)
    if target is None:
        raise SystemExit(
            "provider verification failed: provider target is not configured"
        )

    commit_sha = settings.git_commit.strip()
    if len(commit_sha) != 40:
        raise SystemExit(
            "provider verification failed: HAMOON_GIT_COMMIT must be exact SHA"
        )

    try:
        request, receipt = await verify_provider_integration(
            provider_id=provider_id,
            target=target,
            commit_sha=commit_sha,
            timeout_seconds=settings.provider_dispatch_timeout_seconds,
        )
    except ProviderIntegrationVerificationError as exc:
        raise SystemExit(f"provider verification failed: {exc}") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "provider-verification-request.json").write_text(
        json.dumps(request, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "provider-verification-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: execute_provider_integration_verification.py "
            "<provider-id> <output-dir>"
        )
    try:
        provider_id = UUID(sys.argv[1])
    except ValueError as exc:
        raise SystemExit("provider verification failed: provider ID invalid") from exc
    asyncio.run(_run(provider_id, Path(sys.argv[2])))


if __name__ == "__main__":
    main()
