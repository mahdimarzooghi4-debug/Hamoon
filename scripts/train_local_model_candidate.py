#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import cast


class LocalTrainingError(RuntimeError):
    """Local Hamoon model training contract failed safely."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _load_dataset_export(path: Path) -> dict[str, object]:
    try:
        raw = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise LocalTrainingError("TRAINING_DATASET_EXPORT_INVALID") from exc
    if not isinstance(raw, dict):
        raise LocalTrainingError("TRAINING_DATASET_EXPORT_INVALID")
    wrapper = cast(dict[str, object], raw)
    data = wrapper.get("data", wrapper)
    if not isinstance(data, dict):
        raise LocalTrainingError("TRAINING_DATASET_EXPORT_INVALID")
    dataset = cast(dict[str, object], data)
    if dataset.get("status") != "APPROVED":
        raise LocalTrainingError("TRAINING_DATASET_NOT_APPROVED")
    manifest_digest = dataset.get("manifest_digest")
    if not isinstance(manifest_digest, str) or len(manifest_digest) != 64:
        raise LocalTrainingError("TRAINING_DATASET_DIGEST_INVALID")
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        raise LocalTrainingError("TRAINING_DATASET_EMPTY")
    return dataset


def _validate_relative_ref(value: str) -> str:
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
        relative = path.relative_to(output_dir).as_posix()
        files.append(
            {
                "path": relative,
                "sha256": _sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    if not files:
        raise LocalTrainingError("TRAINER_PRODUCED_NO_MODEL_FILES")
    return files


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Train a new Hamoon model generation using a local trainer process. "
            "No AI API or network endpoint is used."
        )
    )
    parser.add_argument("--dataset-export", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--artifact-ref", required=True)
    parser.add_argument("--trainer-path", type=Path, required=True)
    parser.add_argument("--task-class", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--recipe-version", required=True)
    parser.add_argument("--registration-output", type=Path, required=True)
    parser.add_argument("--parent-model-version-id")
    parser.add_argument("--parent-artifact-ref")
    parser.add_argument("--parent-artifact-sha256")
    args = parser.parse_args()

    dataset = _load_dataset_export(args.dataset_export)
    artifact_ref = _validate_relative_ref(args.artifact_ref)
    model_root = args.model_root.expanduser().resolve()
    trainer_path = args.trainer_path.expanduser().resolve()
    if not model_root.is_dir():
        raise LocalTrainingError("LOCAL_MODEL_ROOT_NOT_FOUND")
    if not trainer_path.is_file() or not os.access(trainer_path, os.X_OK):
        raise LocalTrainingError("LOCAL_TRAINER_INVALID")

    output_dir = (model_root / artifact_ref).resolve()
    if model_root not in output_dir.parents:
        raise LocalTrainingError("MODEL_ARTIFACT_REF_INVALID")
    if output_dir.exists():
        raise LocalTrainingError("MODEL_ARTIFACT_ALREADY_EXISTS")
    output_dir.mkdir(parents=True)

    parent_digest = args.parent_artifact_sha256
    if parent_digest is not None and (
        len(parent_digest) != 64
        or any(ch not in "0123456789abcdef" for ch in parent_digest)
    ):
        raise LocalTrainingError("PARENT_MODEL_ARTIFACT_DIGEST_INVALID")
    if bool(args.parent_artifact_ref) != bool(parent_digest):
        raise LocalTrainingError("PARENT_MODEL_ARTIFACT_IDENTITY_INCOMPLETE")

    request = {
        "schema_version": 1,
        "operation": "TRAIN_MODEL_CANDIDATE",
        "task_class": args.task_class,
        "model_id": args.model_id,
        "recipe_version": args.recipe_version,
        "dataset": dataset,
        "parent_model": (
            {
                "artifact_ref": args.parent_artifact_ref,
                "artifact_sha256": parent_digest,
            }
            if parent_digest is not None
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
        "HAMOON_MODEL_ROOT": str(model_root),
    }
    if args.parent_artifact_ref:
        env["HAMOON_PARENT_MODEL_REF"] = args.parent_artifact_ref

    try:
        completed = subprocess.run(
            [str(trainer_path), "train"],
            input=encoded,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=24 * 60 * 60,
            env=env,
            cwd=model_root,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise LocalTrainingError("LOCAL_TRAINER_FAILED") from exc

    if completed.returncode != 0:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise LocalTrainingError("LOCAL_TRAINER_FAILED")

    try:
        response = cast(object, json.loads(completed.stdout.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise LocalTrainingError("LOCAL_TRAINER_RESPONSE_INVALID") from exc
    if not isinstance(response, dict):
        shutil.rmtree(output_dir, ignore_errors=True)
        raise LocalTrainingError("LOCAL_TRAINER_RESPONSE_INVALID")
    trainer_response = cast(dict[str, object], response)
    if (
        trainer_response.get("schema_version") != 1
        or trainer_response.get("status") != "OK"
        or trainer_response.get("model_id") != args.model_id
        or trainer_response.get("external_network_used") is not False
    ):
        shutil.rmtree(output_dir, ignore_errors=True)
        raise LocalTrainingError("LOCAL_TRAINER_RESPONSE_INVALID")

    trained_at = datetime.now(UTC)
    files = _scan_files(output_dir)
    manifest = {
        "schema_version": 1,
        "runtime_contract": "HAMOON_LOCAL_MODEL_V1",
        "model_id": args.model_id,
        "task_class": args.task_class,
        "external_network_required": False,
        "files": files,
        "training": {
            "dataset_id": str(dataset.get("dataset_id")),
            "dataset_version": dataset.get("dataset_version"),
            "dataset_manifest_digest": dataset["manifest_digest"],
            "recipe_version": args.recipe_version,
            "parent_model_artifact_sha256": parent_digest,
            "trained_at": trained_at.isoformat(),
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_sha256 = _sha256_file(manifest_path)

    registration = {
        "task_class": args.task_class,
        "concrete_model_id": args.model_id,
        "artifact_ref": artifact_ref,
        "artifact_sha256": manifest_sha256,
        "parent_model_version_id": args.parent_model_version_id,
        "training_dataset_version_id": dataset["dataset_id"],
        "training_dataset_manifest_digest": dataset["manifest_digest"],
        "training_recipe_version": args.recipe_version,
        "trained_at": trained_at.isoformat(),
    }
    args.registration_output.parent.mkdir(parents=True, exist_ok=True)
    args.registration_output.write_text(
        json.dumps(registration, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
