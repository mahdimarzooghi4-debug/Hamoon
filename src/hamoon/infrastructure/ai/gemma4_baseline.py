from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Final, cast
from uuid import UUID

from hamoon.infrastructure.ai.contracts import AITaskClass


GEMMA4_BASELINE_MODEL_ID: Final = "google/gemma-4-12B-it"
GEMMA4_BASELINE_REVISION: Final = (
    "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7"
)
GEMMA4_BASELINE_MODEL_SHA256: Final = (
    "5a84cb313260ac447237b890387116dfa8682e49a6b44bc585ae8353abbff18d"
)
GEMMA4_BASELINE_TOKENIZER_SHA256: Final = (
    "cc8d3a0ce36466ccc1278bf987df5f71db1719b9ca6b4118264f45cb627bfe0f"
)
GEMMA4_BASELINE_LICENSE: Final = "Apache-2.0"
GEMMA4_BASELINE_FAMILY: Final = "GEMMA4"
GEMMA4_BASELINE_TRAINING_METHOD: Final = "SFT_LORA"
GEMMA4_BASELINE_ARTIFACT_FORMAT: Final = (
    "HAMOON_GEMMA4_PEFT_SAFETENSORS_V1"
)
GEMMA4_BASELINE_PIPELINE_VERSION: Final = (
    "gemma4-12b-it-sft-lora-v1"
)
GEMMA4_CONCRETE_MODEL_ID: Final = (
    f"{GEMMA4_BASELINE_MODEL_ID}@{GEMMA4_BASELINE_REVISION}"
)

_GEMMA4_ARTIFACT_REQUIRED_FILES: Final = (
    "adapter_config.json",
    "adapter_model.safetensors",
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class Gemma4LoRAArtifactManifest:
    format_version: str
    model_family: str
    base_model_id: str
    base_model_revision: str
    base_model_sha256: str
    license: str
    training_method: str
    training_pipeline_version: str
    training_config_sha256: str
    task_class: str
    training_dataset_version_id: str
    training_dataset_manifest_digest: str
    adapter_files: tuple[str, ...]


def canonical_training_config_digest(config: dict[str, object]) -> str:
    encoded = json.dumps(
        config,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_gemma4_lora_manifest(
    *,
    task_class: AITaskClass,
    training_dataset_version_id: UUID,
    training_dataset_manifest_digest: str,
    training_config_sha256: str,
) -> Gemma4LoRAArtifactManifest:
    dataset_digest = training_dataset_manifest_digest.strip().lower()
    config_digest = training_config_sha256.strip().lower()
    if _SHA256_RE.fullmatch(dataset_digest) is None:
        raise ValueError("GEMMA4_TRAINING_DATASET_DIGEST_INVALID")
    if _SHA256_RE.fullmatch(config_digest) is None:
        raise ValueError("GEMMA4_TRAINING_CONFIG_DIGEST_INVALID")
    return Gemma4LoRAArtifactManifest(
        format_version=GEMMA4_BASELINE_ARTIFACT_FORMAT,
        model_family=GEMMA4_BASELINE_FAMILY,
        base_model_id=GEMMA4_BASELINE_MODEL_ID,
        base_model_revision=GEMMA4_BASELINE_REVISION,
        base_model_sha256=GEMMA4_BASELINE_MODEL_SHA256,
        license=GEMMA4_BASELINE_LICENSE,
        training_method=GEMMA4_BASELINE_TRAINING_METHOD,
        training_pipeline_version=GEMMA4_BASELINE_PIPELINE_VERSION,
        training_config_sha256=config_digest,
        task_class=task_class.value,
        training_dataset_version_id=str(training_dataset_version_id),
        training_dataset_manifest_digest=dataset_digest,
        adapter_files=_GEMMA4_ARTIFACT_REQUIRED_FILES,
    )


def encode_gemma4_lora_manifest(
    manifest: Gemma4LoRAArtifactManifest,
) -> bytes:
    return json.dumps(
        asdict(manifest),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def decode_gemma4_lora_manifest(
    content: bytes,
) -> Gemma4LoRAArtifactManifest:
    raw_value = cast(object, json.loads(content.decode("utf-8")))
    if not isinstance(raw_value, dict):
        raise ValueError("GEMMA4_ARTIFACT_MANIFEST_INVALID")
    raw = cast(dict[str, object], raw_value)
    adapter_files_value = raw.get("adapter_files", ())
    if not isinstance(adapter_files_value, (list, tuple)):
        raise ValueError("GEMMA4_ARTIFACT_FILES_INVALID")
    adapter_files = tuple(
        value
        for value in cast(list[object] | tuple[object, ...], adapter_files_value)
        if isinstance(value, str)
    )
    manifest = Gemma4LoRAArtifactManifest(
        format_version=str(raw.get("format_version", "")),
        model_family=str(raw.get("model_family", "")),
        base_model_id=str(raw.get("base_model_id", "")),
        base_model_revision=str(raw.get("base_model_revision", "")),
        base_model_sha256=str(raw.get("base_model_sha256", "")),
        license=str(raw.get("license", "")),
        training_method=str(raw.get("training_method", "")),
        training_pipeline_version=str(raw.get("training_pipeline_version", "")),
        training_config_sha256=str(raw.get("training_config_sha256", "")),
        task_class=str(raw.get("task_class", "")),
        training_dataset_version_id=str(
            raw.get("training_dataset_version_id", "")
        ),
        training_dataset_manifest_digest=str(
            raw.get("training_dataset_manifest_digest", "")
        ),
        adapter_files=adapter_files,
    )
    if manifest.format_version != GEMMA4_BASELINE_ARTIFACT_FORMAT:
        raise ValueError("GEMMA4_ARTIFACT_FORMAT_UNSUPPORTED")
    if manifest.model_family != GEMMA4_BASELINE_FAMILY:
        raise ValueError("GEMMA4_ARTIFACT_MODEL_FAMILY_MISMATCH")
    if manifest.base_model_id != GEMMA4_BASELINE_MODEL_ID:
        raise ValueError("GEMMA4_ARTIFACT_BASE_MODEL_MISMATCH")
    if manifest.base_model_revision != GEMMA4_BASELINE_REVISION:
        raise ValueError("GEMMA4_ARTIFACT_BASE_REVISION_MISMATCH")
    if manifest.base_model_sha256 != GEMMA4_BASELINE_MODEL_SHA256:
        raise ValueError("GEMMA4_ARTIFACT_BASE_DIGEST_MISMATCH")
    if manifest.training_method != GEMMA4_BASELINE_TRAINING_METHOD:
        raise ValueError("GEMMA4_ARTIFACT_TRAINING_METHOD_MISMATCH")
    if manifest.training_pipeline_version != GEMMA4_BASELINE_PIPELINE_VERSION:
        raise ValueError("GEMMA4_ARTIFACT_PIPELINE_MISMATCH")
    if _SHA256_RE.fullmatch(manifest.training_config_sha256) is None:
        raise ValueError("GEMMA4_TRAINING_CONFIG_DIGEST_INVALID")
    if manifest.adapter_files != _GEMMA4_ARTIFACT_REQUIRED_FILES:
        raise ValueError("GEMMA4_ARTIFACT_FILES_INVALID")
    return manifest
