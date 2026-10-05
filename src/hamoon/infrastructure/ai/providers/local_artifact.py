from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from hamoon.infrastructure.ai.contracts import (
    ProviderStructuredRequest,
    ProviderStructuredResponse,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class LocalModelRuntimeError(RuntimeError):
    """Local Hamoon model runtime failed safely."""


@dataclass(frozen=True, slots=True)
class LocalModelArtifact:
    root: Path
    manifest_path: Path
    model_id: str
    manifest_sha256: str
    training_dataset_manifest_digest: str
    training_recipe_version: str
    parent_model_artifact_sha256: str | None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_child(root: Path, relative: str) -> Path:
    relative_path = Path(relative)
    if relative_path.is_absolute() or any(
        part in {"", ".", ".."} for part in relative_path.parts
    ):
        raise LocalModelRuntimeError("LOCAL_MODEL_ARTIFACT_PATH_INVALID")
    current = root
    for part in relative_path.parts:
        current = current / part
        if current.is_symlink():
            raise LocalModelRuntimeError("LOCAL_MODEL_ARTIFACT_SYMLINK_FORBIDDEN")
    candidate = current.resolve()
    if root != candidate and root not in candidate.parents:
        raise LocalModelRuntimeError("LOCAL_MODEL_ARTIFACT_PATH_INVALID")
    return candidate


def load_local_model_artifact(
    *,
    model_root: Path,
    artifact_ref: str,
    expected_manifest_sha256: str,
    expected_model_id: str,
) -> LocalModelArtifact:
    root = model_root.resolve()
    if not root.is_dir():
        raise LocalModelRuntimeError("LOCAL_MODEL_ROOT_NOT_FOUND")

    artifact_dir = _safe_child(root, artifact_ref)
    if not artifact_dir.is_dir():
        raise LocalModelRuntimeError("LOCAL_MODEL_ARTIFACT_NOT_FOUND")

    manifest_path = artifact_dir / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise LocalModelRuntimeError("LOCAL_MODEL_MANIFEST_NOT_FOUND")

    manifest_sha256 = _sha256_file(manifest_path)
    if _SHA256_RE.fullmatch(expected_manifest_sha256) is None:
        raise LocalModelRuntimeError("LOCAL_MODEL_MANIFEST_DIGEST_INVALID")
    if manifest_sha256 != expected_manifest_sha256:
        raise LocalModelRuntimeError("LOCAL_MODEL_MANIFEST_DIGEST_MISMATCH")

    try:
        raw = cast(object, json.loads(manifest_path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise LocalModelRuntimeError("LOCAL_MODEL_MANIFEST_INVALID") from exc
    if not isinstance(raw, dict):
        raise LocalModelRuntimeError("LOCAL_MODEL_MANIFEST_INVALID")
    manifest = cast(dict[str, object], raw)

    if manifest.get("schema_version") != 1:
        raise LocalModelRuntimeError("LOCAL_MODEL_MANIFEST_SCHEMA_UNSUPPORTED")
    if manifest.get("runtime_contract") != "HAMOON_LOCAL_MODEL_V1":
        raise LocalModelRuntimeError("LOCAL_MODEL_RUNTIME_CONTRACT_INVALID")
    if manifest.get("model_id") != expected_model_id:
        raise LocalModelRuntimeError("LOCAL_MODEL_ID_MISMATCH")
    if manifest.get("external_network_required") is not False:
        raise LocalModelRuntimeError("LOCAL_MODEL_EXTERNAL_NETWORK_FORBIDDEN")

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise LocalModelRuntimeError("LOCAL_MODEL_FILES_REQUIRED")
    for item in files:
        if not isinstance(item, dict):
            raise LocalModelRuntimeError("LOCAL_MODEL_FILE_ENTRY_INVALID")
        relative = item.get("path")
        sha256 = item.get("sha256")
        size_bytes = item.get("size_bytes")
        if (
            not isinstance(relative, str)
            or not relative
            or not isinstance(sha256, str)
            or _SHA256_RE.fullmatch(sha256) is None
            or not isinstance(size_bytes, int)
            or size_bytes < 1
        ):
            raise LocalModelRuntimeError("LOCAL_MODEL_FILE_ENTRY_INVALID")
        file_path = _safe_child(artifact_dir, relative)
        if not file_path.is_file() or file_path.is_symlink():
            raise LocalModelRuntimeError("LOCAL_MODEL_FILE_NOT_FOUND")
        stat = file_path.stat()
        if stat.st_size != size_bytes:
            raise LocalModelRuntimeError("LOCAL_MODEL_FILE_SIZE_MISMATCH")
        if _sha256_file(file_path) != sha256:
            raise LocalModelRuntimeError("LOCAL_MODEL_FILE_DIGEST_MISMATCH")

    training = manifest.get("training")
    if not isinstance(training, dict):
        raise LocalModelRuntimeError("LOCAL_MODEL_TRAINING_LINEAGE_REQUIRED")
    dataset_digest = training.get("dataset_manifest_digest")
    recipe_version = training.get("recipe_version")
    parent_digest = training.get("parent_model_artifact_sha256")
    if (
        not isinstance(dataset_digest, str)
        or _SHA256_RE.fullmatch(dataset_digest) is None
    ):
        raise LocalModelRuntimeError("LOCAL_MODEL_DATASET_LINEAGE_INVALID")
    if not isinstance(recipe_version, str) or not recipe_version.strip():
        raise LocalModelRuntimeError("LOCAL_MODEL_RECIPE_LINEAGE_INVALID")
    if parent_digest is not None and (
        not isinstance(parent_digest, str)
        or _SHA256_RE.fullmatch(parent_digest) is None
    ):
        raise LocalModelRuntimeError("LOCAL_MODEL_PARENT_LINEAGE_INVALID")

    return LocalModelArtifact(
        root=artifact_dir,
        manifest_path=manifest_path,
        model_id=expected_model_id,
        manifest_sha256=manifest_sha256,
        training_dataset_manifest_digest=dataset_digest,
        training_recipe_version=recipe_version,
        parent_model_artifact_sha256=cast(str | None, parent_digest),
    )


class LocalArtifactAIProvider:
    code = "HAMOON_LOCAL"

    def __init__(
        self,
        *,
        model_root: Path,
        runner_path: Path,
        timeout_seconds: float = 120.0,
    ) -> None:
        root = model_root.expanduser().resolve()
        runner = runner_path.expanduser().resolve()
        if not root.is_dir():
            raise ValueError("LOCAL_AI_MODEL_ROOT_INVALID")
        if not runner.is_file() or not os.access(runner, os.X_OK):
            raise ValueError("LOCAL_AI_RUNNER_INVALID")
        if timeout_seconds <= 0:
            raise ValueError("LOCAL_AI_TIMEOUT_INVALID")
        self._model_root = root
        self._runner_path = runner
        self._timeout_seconds = timeout_seconds

    async def generate_structured(
        self,
        request: ProviderStructuredRequest,
    ) -> ProviderStructuredResponse:
        if request.model_artifact_ref is None or request.model_artifact_sha256 is None:
            raise LocalModelRuntimeError("LOCAL_MODEL_ARTIFACT_IDENTITY_REQUIRED")

        artifact = load_local_model_artifact(
            model_root=self._model_root,
            artifact_ref=request.model_artifact_ref,
            expected_manifest_sha256=request.model_artifact_sha256,
            expected_model_id=request.model_id,
        )
        payload: dict[str, JsonValue] = {
            "schema_version": 1,
            "operation": "GENERATE_STRUCTURED",
            "task_class": request.task_class.value,
            "model_id": request.model_id,
            "model_artifact_sha256": artifact.manifest_sha256,
            "model_alias": request.model_alias,
            "prompt_policy_version": request.prompt_policy_version,
            "output_schema_version": request.output_schema_version,
            "feature_schema_version": request.feature_schema_version,
            "instructions": request.instructions,
            "output_schema": request.output_schema,
            "features": request.features,
            "correlation_id": request.correlation_id,
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        env = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "HAMOON_AI_NETWORK_POLICY": "DENY",
            "HAMOON_MODEL_ROOT": str(artifact.root),
            "HAMOON_MODEL_MANIFEST": str(artifact.manifest_path),
        }
        try:
            completed = await asyncio.to_thread(
                subprocess.run,
                [str(self._runner_path), "infer"],
                input=encoded,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=self._timeout_seconds,
                env=env,
                cwd=artifact.root,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LocalModelRuntimeError("LOCAL_AI_RUNNER_FAILED") from exc
        if completed.returncode != 0:
            raise LocalModelRuntimeError("LOCAL_AI_RUNNER_FAILED")
        if len(completed.stdout) > 2 * 1024 * 1024:
            raise LocalModelRuntimeError("LOCAL_AI_OUTPUT_TOO_LARGE")
        try:
            raw = cast(object, json.loads(completed.stdout.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LocalModelRuntimeError("LOCAL_AI_OUTPUT_INVALID") from exc
        if not isinstance(raw, dict):
            raise LocalModelRuntimeError("LOCAL_AI_OUTPUT_INVALID")
        body = cast(dict[str, object], raw)
        if body.get("schema_version") != 1 or body.get("status") != "OK":
            raise LocalModelRuntimeError("LOCAL_AI_OUTPUT_INVALID")
        if body.get("model_id") != request.model_id:
            raise LocalModelRuntimeError("LOCAL_AI_MODEL_ID_MISMATCH")
        if body.get("model_artifact_sha256") != artifact.manifest_sha256:
            raise LocalModelRuntimeError("LOCAL_AI_MODEL_ARTIFACT_MISMATCH")
        output = body.get("output")
        if not isinstance(output, dict):
            raise LocalModelRuntimeError("LOCAL_AI_OUTPUT_INVALID")

        return ProviderStructuredResponse(
            provider_code=self.code,
            model_id=request.model_id,
            model_artifact_sha256=artifact.manifest_sha256,
            output=cast(dict[str, JsonValue], output),
        )
