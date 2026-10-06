from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Final, cast
from uuid import UUID

from hamoon.infrastructure.ai.contracts import AITaskClass


QWEN3_BASELINE_MODEL_ID: Final = "Qwen/Qwen3-4B-Instruct-2507"
QWEN3_BASELINE_REVISION: Final = (
    "cdbee75f17c01a7cc42f958dc650907174af0554"
)
QWEN3_BASELINE_LICENSE: Final = "Apache-2.0"
QWEN3_BASELINE_FAMILY: Final = "QWEN3"
QWEN3_BASELINE_TRAINING_METHOD: Final = "SFT_LORA"
QWEN3_BASELINE_ARTIFACT_FORMAT: Final = "HAMOON_QWEN3_PEFT_SAFETENSORS_V1"
QWEN3_BASELINE_PIPELINE_VERSION: Final = "qwen3-4b-instruct-2507-sft-lora-v1"

_QWEN3_ARTIFACT_REQUIRED_FILES: Final = (
    "adapter_config.json",
    "adapter_model.safetensors",
)


@dataclass(frozen=True, slots=True)
class Qwen3LoRAArtifactManifest:
    format_version: str
    model_family: str
    base_model_id: str
    base_model_revision: str
    license: str
    training_method: str
    training_pipeline_version: str
    task_class: str
    training_dataset_version_id: str
    training_dataset_manifest_digest: str
    adapter_files: tuple[str, ...]


def build_qwen3_lora_manifest(
    *,
    task_class: AITaskClass,
    training_dataset_version_id: UUID,
    training_dataset_manifest_digest: str,
) -> Qwen3LoRAArtifactManifest:
    return Qwen3LoRAArtifactManifest(
        format_version=QWEN3_BASELINE_ARTIFACT_FORMAT,
        model_family=QWEN3_BASELINE_FAMILY,
        base_model_id=QWEN3_BASELINE_MODEL_ID,
        base_model_revision=QWEN3_BASELINE_REVISION,
        license=QWEN3_BASELINE_LICENSE,
        training_method=QWEN3_BASELINE_TRAINING_METHOD,
        training_pipeline_version=QWEN3_BASELINE_PIPELINE_VERSION,
        task_class=task_class.value,
        training_dataset_version_id=str(training_dataset_version_id),
        training_dataset_manifest_digest=(
            training_dataset_manifest_digest.strip().lower()
        ),
        adapter_files=_QWEN3_ARTIFACT_REQUIRED_FILES,
    )


def encode_qwen3_lora_manifest(
    manifest: Qwen3LoRAArtifactManifest,
) -> bytes:
    return json.dumps(
        asdict(manifest),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def decode_qwen3_lora_manifest(
    content: bytes,
) -> Qwen3LoRAArtifactManifest:
    raw_value = cast(object, json.loads(content.decode("utf-8")))
    if not isinstance(raw_value, dict):
        raise ValueError("QWEN3_ARTIFACT_MANIFEST_INVALID")
    raw = cast(dict[str, object], raw_value)

    adapter_files_value = raw.get("adapter_files", ())
    if not isinstance(adapter_files_value, (list, tuple)):
        raise ValueError("QWEN3_ARTIFACT_FILES_INVALID")
    adapter_files = cast(
        list[object] | tuple[object, ...],
        adapter_files_value,
    )

    manifest = Qwen3LoRAArtifactManifest(
        format_version=str(raw.get("format_version", "")),
        model_family=str(raw.get("model_family", "")),
        base_model_id=str(raw.get("base_model_id", "")),
        base_model_revision=str(raw.get("base_model_revision", "")),
        license=str(raw.get("license", "")),
        training_method=str(raw.get("training_method", "")),
        training_pipeline_version=str(raw.get("training_pipeline_version", "")),
        task_class=str(raw.get("task_class", "")),
        training_dataset_version_id=str(
            raw.get("training_dataset_version_id", "")
        ),
        training_dataset_manifest_digest=str(
            raw.get("training_dataset_manifest_digest", "")
        ),
        adapter_files=tuple(
            value
            for value in adapter_files
            if isinstance(value, str)
        ),
    )
    if manifest.format_version != QWEN3_BASELINE_ARTIFACT_FORMAT:
        raise ValueError("QWEN3_ARTIFACT_FORMAT_UNSUPPORTED")
    if manifest.model_family != QWEN3_BASELINE_FAMILY:
        raise ValueError("QWEN3_ARTIFACT_MODEL_FAMILY_MISMATCH")
    if manifest.base_model_id != QWEN3_BASELINE_MODEL_ID:
        raise ValueError("QWEN3_ARTIFACT_BASE_MODEL_MISMATCH")
    if manifest.base_model_revision != QWEN3_BASELINE_REVISION:
        raise ValueError("QWEN3_ARTIFACT_BASE_REVISION_MISMATCH")
    if manifest.training_method != QWEN3_BASELINE_TRAINING_METHOD:
        raise ValueError("QWEN3_ARTIFACT_TRAINING_METHOD_MISMATCH")
    if manifest.training_pipeline_version != QWEN3_BASELINE_PIPELINE_VERSION:
        raise ValueError("QWEN3_ARTIFACT_PIPELINE_MISMATCH")
    if manifest.adapter_files != _QWEN3_ARTIFACT_REQUIRED_FILES:
        raise ValueError("QWEN3_ARTIFACT_FILES_INVALID")
    return manifest
