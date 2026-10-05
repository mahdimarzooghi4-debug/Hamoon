#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from hamoon.infrastructure.ai.local_training import (
    LocalTrainingError,
    train_local_model_candidate,
)


def _load_dataset_export(path: Path) -> dict[str, object]:
    try:
        raw = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("local training failed: TRAINING_DATASET_EXPORT_INVALID") from exc
    if not isinstance(raw, dict):
        raise SystemExit("local training failed: TRAINING_DATASET_EXPORT_INVALID")
    wrapper = cast(dict[str, object], raw)
    data = wrapper.get("data", wrapper)
    if not isinstance(data, dict):
        raise SystemExit("local training failed: TRAINING_DATASET_EXPORT_INVALID")
    return cast(dict[str, object], data)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Train a new Hamoon model generation with a local trainer. "
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

    try:
        result = train_local_model_candidate(
            dataset=_load_dataset_export(args.dataset_export),
            model_root=args.model_root,
            artifact_ref=args.artifact_ref,
            trainer_path=args.trainer_path,
            task_class=args.task_class,
            model_id=args.model_id,
            recipe_version=args.recipe_version,
            parent_artifact_ref=args.parent_artifact_ref,
            parent_artifact_sha256=args.parent_artifact_sha256,
        )
    except LocalTrainingError as exc:
        raise SystemExit(f"local training failed: {exc}") from exc

    registration = {
        "task_class": args.task_class,
        "concrete_model_id": result.model_id,
        "artifact_ref": result.artifact_ref,
        "artifact_sha256": result.artifact_sha256,
        "parent_model_version_id": args.parent_model_version_id,
        "parent_model_artifact_sha256": result.parent_model_artifact_sha256,
        "training_dataset_version_id": _load_dataset_export(
            args.dataset_export
        )["dataset_id"],
        "training_dataset_manifest_digest": (
            result.training_dataset_manifest_digest
        ),
        "training_recipe_version": result.training_recipe_version,
        "trained_at": result.trained_at.isoformat(),
    }
    args.registration_output.parent.mkdir(parents=True, exist_ok=True)
    args.registration_output.write_text(
        json.dumps(registration, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
