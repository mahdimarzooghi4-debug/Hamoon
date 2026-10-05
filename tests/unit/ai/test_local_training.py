from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def _write_dataset(path: Path, *, status: str = "APPROVED") -> str:
    digest = "d" * 64
    payload = {
        "data": {
            "dataset_id": "11111111-1111-1111-1111-111111111111",
            "dataset_version": "outcome-v1",
            "status": status,
            "manifest_digest": digest,
            "selection_policy_version": "outcome-learning-selection-v1",
            "cases": [
                {
                    "case_id": "case-1",
                    "input": {"delta": {"e": "0.2"}},
                    "expert_classification": "IMPROVED",
                    "source_refs": ["outcome:1"],
                }
            ],
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return digest


def _write_trainer(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

request = json.loads(sys.stdin.read())
out = Path(os.environ["HAMOON_TRAINING_OUTPUT_DIR"])
(out / "weights.bin").write_bytes(
    ("trained:" + request["dataset"]["manifest_digest"]).encode("utf-8")
)
sys.stdout.write(json.dumps({
    "schema_version": 1,
    "status": "OK",
    "model_id": request["model_id"],
    "external_network_used": False,
}))
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_local_training_builds_immutable_model_package(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    dataset_digest = _write_dataset(dataset)
    model_root = tmp_path / "models"
    model_root.mkdir()
    trainer = tmp_path / "trainer"
    _write_trainer(trainer)
    registration = tmp_path / "registration.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/train_local_model_candidate.py",
            "--dataset-export",
            str(dataset),
            "--model-root",
            str(model_root),
            "--artifact-ref",
            "outcome/generation-2",
            "--trainer-path",
            str(trainer),
            "--task-class",
            "OUTCOME_INTERPRETATION",
            "--model-id",
            "hamoon-outcome-local-v2",
            "--recipe-version",
            "outcome-training-v2",
            "--registration-output",
            str(registration),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    artifact = model_root / "outcome/generation-2"
    manifest_path = artifact / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    registration_payload = json.loads(registration.read_text())

    assert manifest["runtime_contract"] == "HAMOON_LOCAL_MODEL_V1"
    assert manifest["external_network_required"] is False
    assert manifest["training"]["dataset_manifest_digest"] == dataset_digest
    assert manifest["training"]["recipe_version"] == "outcome-training-v2"
    assert registration_payload["training_dataset_manifest_digest"] == dataset_digest
    assert registration_payload["artifact_sha256"] == hashlib.sha256(
        manifest_path.read_bytes()
    ).hexdigest()


def test_local_training_rejects_unapproved_dataset(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    _write_dataset(dataset, status="DRAFT")
    model_root = tmp_path / "models"
    model_root.mkdir()
    trainer = tmp_path / "trainer"
    _write_trainer(trainer)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/train_local_model_candidate.py",
            "--dataset-export",
            str(dataset),
            "--model-root",
            str(model_root),
            "--artifact-ref",
            "outcome/generation-2",
            "--trainer-path",
            str(trainer),
            "--task-class",
            "OUTCOME_INTERPRETATION",
            "--model-id",
            "hamoon-outcome-local-v2",
            "--recipe-version",
            "outcome-training-v2",
            "--registration-output",
            str(tmp_path / "registration.json"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "TRAINING_DATASET_NOT_APPROVED" in result.stderr


def test_local_training_refuses_existing_artifact_directory(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    _write_dataset(dataset)
    model_root = tmp_path / "models"
    existing = model_root / "outcome/generation-2"
    existing.mkdir(parents=True)
    trainer = tmp_path / "trainer"
    _write_trainer(trainer)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/train_local_model_candidate.py",
            "--dataset-export",
            str(dataset),
            "--model-root",
            str(model_root),
            "--artifact-ref",
            "outcome/generation-2",
            "--trainer-path",
            str(trainer),
            "--task-class",
            "OUTCOME_INTERPRETATION",
            "--model-id",
            "hamoon-outcome-local-v2",
            "--recipe-version",
            "outcome-training-v2",
            "--registration-output",
            str(tmp_path / "registration.json"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "MODEL_ARTIFACT_ALREADY_EXISTS" in result.stderr
