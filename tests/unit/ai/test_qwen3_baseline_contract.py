from uuid import UUID

import pytest

from hamoon.infrastructure.ai.contracts import AITaskClass
from hamoon.infrastructure.ai.qwen3_baseline import (
    QWEN3_BASELINE_ARTIFACT_FORMAT,
    QWEN3_BASELINE_MODEL_ID,
    QWEN3_BASELINE_PIPELINE_VERSION,
    QWEN3_BASELINE_REVISION,
    QWEN3_BASELINE_TRAINING_METHOD,
    build_qwen3_lora_manifest,
    decode_qwen3_lora_manifest,
    encode_qwen3_lora_manifest,
)


DATASET_ID = UUID("11111111-2222-3333-4444-555555555555")


def test_qwen3_baseline_is_pinned_and_reproducible() -> None:
    manifest = build_qwen3_lora_manifest(
        task_class=AITaskClass.DIAGNOSIS,
        training_dataset_version_id=DATASET_ID,
        training_dataset_manifest_digest="a" * 64,
    )

    assert manifest.base_model_id == "Qwen/Qwen3-4B-Instruct-2507"
    assert manifest.base_model_id == QWEN3_BASELINE_MODEL_ID
    assert (
        manifest.base_model_revision
        == "cdbee75f17c01a7cc42f958dc650907174af0554"
    )
    assert manifest.base_model_revision == QWEN3_BASELINE_REVISION
    assert manifest.training_method == "SFT_LORA"
    assert manifest.training_method == QWEN3_BASELINE_TRAINING_METHOD
    assert manifest.format_version == "HAMOON_QWEN3_PEFT_SAFETENSORS_V1"
    assert manifest.format_version == QWEN3_BASELINE_ARTIFACT_FORMAT
    assert (
        manifest.training_pipeline_version
        == "qwen3-4b-instruct-2507-sft-lora-v1"
    )
    assert manifest.training_pipeline_version == QWEN3_BASELINE_PIPELINE_VERSION
    assert manifest.adapter_files == (
        "adapter_config.json",
        "adapter_model.safetensors",
    )


def test_qwen3_manifest_encoding_is_canonical() -> None:
    manifest = build_qwen3_lora_manifest(
        task_class=AITaskClass.OUTCOME_INTERPRETATION,
        training_dataset_version_id=DATASET_ID,
        training_dataset_manifest_digest="B" * 64,
    )

    first = encode_qwen3_lora_manifest(manifest)
    second = encode_qwen3_lora_manifest(manifest)

    assert first == second
    assert decode_qwen3_lora_manifest(first) == manifest
    assert manifest.training_dataset_manifest_digest == "b" * 64


def test_qwen3_manifest_rejects_unpinned_base_revision() -> None:
    manifest = build_qwen3_lora_manifest(
        task_class=AITaskClass.PRESCRIPTION,
        training_dataset_version_id=DATASET_ID,
        training_dataset_manifest_digest="c" * 64,
    )
    encoded = encode_qwen3_lora_manifest(manifest).replace(
        QWEN3_BASELINE_REVISION.encode(),
        b"0" * 40,
    )

    with pytest.raises(
        ValueError,
        match="QWEN3_ARTIFACT_BASE_REVISION_MISMATCH",
    ):
        decode_qwen3_lora_manifest(encoded)
