from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from uuid import UUID

import pytest

from hamoon.infrastructure.ai.contracts import (
    AITaskClass,
    ProviderStructuredRequest,
)
from hamoon.infrastructure.ai.providers.local_artifact import (
    LocalArtifactAIProvider,
    LocalModelRuntimeError,
)


def _write_artifact(root: Path) -> tuple[str, str]:
    artifact_ref = "diagnosis/generation-1"
    artifact = root / artifact_ref
    artifact.mkdir(parents=True)
    weights = artifact / "weights.bin"
    weights.write_bytes(b"hamoon-local-model-weights")
    manifest = {
        "schema_version": 1,
        "runtime_contract": "HAMOON_LOCAL_MODEL_V1",
        "model_id": "hamoon-diagnosis-local-v1",
        "task_class": "DIAGNOSIS",
        "external_network_required": False,
        "files": [
            {
                "path": "weights.bin",
                "sha256": hashlib.sha256(weights.read_bytes()).hexdigest(),
                "size_bytes": weights.stat().st_size,
            }
        ],
        "training": {
            "dataset_id": "11111111-1111-1111-1111-111111111111",
            "dataset_version": "v1",
            "dataset_manifest_digest": "b" * 64,
            "recipe_version": "diagnosis-train-v1",
            "parent_model_artifact_sha256": None,
            "trained_at": "2026-10-05T12:00:00+00:00",
        },
    }
    manifest_path = artifact / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact_ref, hashlib.sha256(manifest_path.read_bytes()).hexdigest()


def _write_runner(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

request = json.loads(sys.stdin.read())
response = {
    "schema_version": 1,
    "status": "OK",
    "model_id": request["model_id"],
    "model_artifact_sha256": request["model_artifact_sha256"],
    "output": {
        "schema_version": "diagnosis-v1",
        "external_ai_credential_visible": bool(
            os.getenv("OPENAI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        ),
        "network_policy": os.getenv("HAMOON_AI_NETWORK_POLICY"),
    },
}
sys.stdout.write(json.dumps(response))
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _request(artifact_ref: str, digest: str) -> ProviderStructuredRequest:
    return ProviderStructuredRequest(
        task_class=AITaskClass.DIAGNOSIS,
        model_id="hamoon-diagnosis-local-v1",
        model_alias="hamoon.diagnosis.local",
        model_artifact_ref=artifact_ref,
        model_artifact_sha256=digest,
        prompt_policy_version="diagnosis-prompt-v1",
        output_schema_version="diagnosis-v1",
        feature_schema_version="diagnosis-input-v1",
        instructions="Use only supplied features.",
        output_schema={"type": "object"},
        features={"pgor.O": "0.4"},
        correlation_id=str(UUID("22222222-2222-2222-2222-222222222222")),
    )


@pytest.mark.asyncio
async def test_local_artifact_provider_runs_without_ai_api_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_root = tmp_path / "models"
    model_root.mkdir()
    artifact_ref, digest = _write_artifact(model_root)
    runner = tmp_path / "hamoon-local-ai-runner"
    _write_runner(runner)

    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-leak")

    provider = LocalArtifactAIProvider(
        model_root=model_root,
        runner_path=runner,
    )
    result = await provider.generate_structured(
        _request(artifact_ref, digest)
    )

    assert result.provider_code == "HAMOON_LOCAL"
    assert result.model_artifact_sha256 == digest
    assert result.output["external_ai_credential_visible"] is False
    assert result.output["network_policy"] == "DENY"


@pytest.mark.asyncio
async def test_local_artifact_provider_rejects_manifest_identity_drift(
    tmp_path: Path,
) -> None:
    model_root = tmp_path / "models"
    model_root.mkdir()
    artifact_ref, _digest = _write_artifact(model_root)
    runner = tmp_path / "runner"
    _write_runner(runner)

    provider = LocalArtifactAIProvider(
        model_root=model_root,
        runner_path=runner,
    )
    with pytest.raises(
        LocalModelRuntimeError,
        match="LOCAL_MODEL_MANIFEST_DIGEST_MISMATCH",
    ):
        await provider.generate_structured(
            _request(artifact_ref, "c" * 64)
        )


@pytest.mark.asyncio
async def test_local_artifact_provider_rejects_tampered_model_file(
    tmp_path: Path,
) -> None:
    model_root = tmp_path / "models"
    model_root.mkdir()
    artifact_ref, digest = _write_artifact(model_root)
    (model_root / artifact_ref / "weights.bin").write_bytes(b"tampered")
    runner = tmp_path / "runner"
    _write_runner(runner)

    provider = LocalArtifactAIProvider(
        model_root=model_root,
        runner_path=runner,
    )
    with pytest.raises(
        LocalModelRuntimeError,
        match="LOCAL_MODEL_FILE_(SIZE|DIGEST)_MISMATCH",
    ):
        await provider.generate_structured(
            _request(artifact_ref, digest)
        )


def test_local_artifact_provider_rejects_missing_local_runtime(
    tmp_path: Path,
) -> None:
    model_root = tmp_path / "models"
    model_root.mkdir()

    with pytest.raises(ValueError, match="LOCAL_AI_RUNNER_INVALID"):
        LocalArtifactAIProvider(
            model_root=model_root,
            runner_path=tmp_path / "missing-runner",
        )
