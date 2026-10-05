from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast


class LocalTrainingError(RuntimeError):
    """Local Hamoon model training contract failed safely."""


@dataclass(frozen=True, slots=True)
class LocalTrainingResult:
    artifact_ref: str
    artifact_sha256: str
    model_id: str
    training_dataset_manifest_digest: str
    training_recipe_version: str
    parent_model_artifact_sha256: str | None
    trained_at: datetime


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def validate_dataset_export(dataset: dict[str, object]) -> None:
    if dataset.get("status") != "APPROVED":
        raise LocalTrainingError("TRAINING_DATASET_NOT_APPROVED")
    manifest_digest = dataset.get("manifest_digest")
    if not isinstance(manifest_digest, str) or len(manifest_digest) != 64:
        raise LocalTrainingError("TRAINING_DATASET_DIGEST_INVALID")
    if any(ch not in "0123456789abcdef" for ch in manifest_digest):
        raise LocalTrainingError("TRAINING_DATASET_DIGEST_INVALID")
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        raise LocalTrainingError("TRAINING_DATASET_EMPTY")


def validate_artifact_ref(value: str) -> str:
    clean = value.strip().strip("/")
    if not clean or ".." in clean.split("/"):
        raise LocalTrainingError("MODEL_ARTIFACT_REF_INVALID")
    return clean


def _scan_files(output_dir: Path) -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    for path in sorted(output_dir.rglob("*")):
        if path.name == "manifest.json":
            continue
        if path.is_symlink():
            raise LocalTrainingError("MODEL_ARTIFACT_SYMLINK_FORBIDDEN")
        if not path.is_file():
            continue
        files.append(
            {
                "path": path.relative_to(output_dir).as_posix(),
                "sha256": _sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    if not files:
        raise LocalTrainingError("TRAINER_PRODUCED_NO_MODEL_FILES")
    return files


def train_local_model_candidate(
    *,
    dataset: dict[str, object],
    model_root: Path,
    artifact_ref: str,
    trainer_path: Path,
    task_class: str,
    model_id: str,
    recipe_version: str,
    parent_artifact_ref: str | None = None,
    parent_artifact_sha256: str | None = None,
    timeout_seconds: float = 24 * 60 * 60,
) -> LocalTrainingResult:
    validate_dataset_export(dataset)
    clean_ref = validate_artifact_ref(artifact_ref)
    root = model_root.expanduser().resolve()
    trainer = trainer_path.expanduser().resolve()
    if not root.is_dir():
        raise LocalTrainingError("LOCAL_MODEL_ROOT_NOT_FOUND")
    if not trainer.is_file() or not os.access(trainer, os.X_OK):
        raise LocalTrainingError("LOCAL_TRAINER_INVALID")
    if timeout_seconds <= 0:
        raise LocalTrainingError("LOCAL_TRAINER_TIMEOUT_INVALID")
    if not model_id.strip() or not recipe_version.strip() or not task_class.strip():
        raise LocalTrainingError("LOCAL_TRAINING_METADATA_REQUIRED")

    if bool(parent_artifact_ref) != bool(parent_artifact_sha256):
        raise LocalTrainingError("PARENT_MODEL_ARTIFACT_IDENTITY_INCOMPLETE")
    if parent_artifact_sha256 is not None and (
        len(parent_artifact_sha256) != 64
        or any(ch not in "0123456789abcdef" for ch in parent_artifact_sha256)
    ):
        raise LocalTrainingError("PARENT_MODEL_ARTIFACT_DIGEST_INVALID")

    output_dir = (root / clean_ref).resolve()
    if root not in output_dir.parents:
        raise LocalTrainingError("MODEL_ARTIFACT_REF_INVALID")
    if output_dir.exists():
        raise LocalTrainingError("MODEL_ARTIFACT_ALREADY_EXISTS")
    output_dir.mkdir(parents=True)

    request = {
        "schema_version": 1,
        "operation": "TRAIN_MODEL_CANDIDATE",
        "task_class": task_class,
        "model_id": model_id,
        "recipe_version": recipe_version,
        "dataset": dataset,
        "parent_model": (
            {
                "artifact_ref": parent_artifact_ref,
                "artifact_sha256": parent_artifact_sha256,
            }
            if parent_artifact_sha256 is not None
            else None
        ),
    }
    encoded = json.dumps(
        request,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    env = {
        "PATH": os.environ.get("PATH", ""),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "HAMOON_AI_NETWORK_POLICY": "DENY",
        "HAMOON_TRAINING_OUTPUT_DIR": str(output_dir),
        "HAMOON_MODEL_ROOT": str(root),
    }
    if parent_artifact_ref:
        env["HAMOON_PARENT_MODEL_REF"] = parent_artifact_ref

    try:
        completed = subprocess.run(
            [str(trainer), "train"],
            input=encoded,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
            env=env,
            cwd=root,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise LocalTrainingError("LOCAL_TRAINER_FAILED") from exc

    if completed.returncode != 0:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise LocalTrainingError("LOCAL_TRAINER_FAILED")
    try:
        raw = cast(object, json.loads(completed.stdout.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise LocalTrainingError("LOCAL_TRAINER_RESPONSE_INVALID") from exc
    if not isinstance(raw, dict):
        shutil.rmtree(output_dir, ignore_errors=True)
        raise LocalTrainingError("LOCAL_TRAINER_RESPONSE_INVALID")
    response = cast(dict[str, object], raw)
    if (
        response.get("schema_version") != 1
        or response.get("status") != "OK"
        or response.get("model_id") != model_id
        or response.get("external_network_used") is not False
    ):
        shutil.rmtree(output_dir, ignore_errors=True)
        raise LocalTrainingError("LOCAL_TRAINER_RESPONSE_INVALID")

    trained_at = datetime.now(UTC)
    manifest = {
        "schema_version": 1,
        "runtime_contract": "HAMOON_LOCAL_MODEL_V1",
        "model_id": model_id,
        "task_class": task_class,
        "external_network_required": False,
        "files": _scan_files(output_dir),
        "training": {
            "dataset_id": str(dataset.get("dataset_id")),
            "dataset_version": dataset.get("dataset_version"),
            "dataset_manifest_digest": dataset["manifest_digest"],
            "recipe_version": recipe_version,
            "parent_model_artifact_sha256": parent_artifact_sha256,
            "trained_at": trained_at.isoformat(),
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return LocalTrainingResult(
        artifact_ref=clean_ref,
        artifact_sha256=_sha256_file(manifest_path),
        model_id=model_id,
        training_dataset_manifest_digest=cast(str, dataset["manifest_digest"]),
        training_recipe_version=recipe_version,
        parent_model_artifact_sha256=parent_artifact_sha256,
        trained_at=trained_at,
    )
