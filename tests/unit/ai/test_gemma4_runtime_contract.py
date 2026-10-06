import hashlib
from pathlib import Path
from uuid import UUID

import pytest

import hamoon.infrastructure.ai.gemma4_runtime as gemma4_runtime_module
from hamoon.infrastructure.ai.contracts import AITaskClass
from hamoon.infrastructure.ai.gemma4_baseline import (
    GEMMA4_BASELINE_ARTIFACT_FORMAT,
    GEMMA4_BASELINE_MODEL_ID,
    GEMMA4_BASELINE_MODEL_SHA256,
    GEMMA4_BASELINE_PIPELINE_VERSION,
    GEMMA4_BASELINE_REVISION,
    GEMMA4_BASELINE_TOKENIZER_SHA256,
    GEMMA4_CONCRETE_MODEL_ID,
    build_gemma4_lora_manifest,
    canonical_training_config_digest,
    decode_gemma4_lora_manifest,
    encode_gemma4_lora_manifest,
)
from hamoon.infrastructure.ai.gemma4_runtime import (
    Gemma4BaseCheckpoint,
    Gemma4GenerationConfig,
    Gemma4LoRATrainingConfig,
    Gemma4RuntimeError,
    _build_adapter_artifact,
    _extract_adapter_artifact,
    _require_supervised_target,
)


DATASET_ID = UUID("11111111-2222-3333-4444-555555555555")


def _training_config() -> str:
    return """{
      "max_sequence_length": 2048,
      "dtype": "bfloat16",
      "device_map": "auto",
      "lora_r": 16,
      "lora_alpha": 32,
      "lora_dropout": 0.05,
      "lora_bias": "none",
      "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
      "training_arguments": {
        "learning_rate": 0.0001,
        "num_train_epochs": 1,
        "per_device_train_batch_size": 1,
        "gradient_accumulation_steps": 8,
        "weight_decay": 0.0,
        "warmup_ratio": 0.0,
        "lr_scheduler_type": "cosine",
        "optim": "adamw_torch",
        "max_grad_norm": 1.0,
        "seed": 42,
        "gradient_checkpointing": true
      }
    }"""


def test_gemma4_baseline_is_pinned_and_reproducible() -> None:
    config = Gemma4LoRATrainingConfig.from_json(_training_config())
    config_digest = canonical_training_config_digest(
        config.canonical_dict()
    )
    manifest = build_gemma4_lora_manifest(
        task_class=AITaskClass.DIAGNOSIS,
        training_dataset_version_id=DATASET_ID,
        training_dataset_manifest_digest="a" * 64,
        training_config_sha256=config_digest,
    )

    assert GEMMA4_BASELINE_MODEL_ID == "google/gemma-4-12B-it"
    assert (
        GEMMA4_BASELINE_REVISION
        == "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7"
    )
    assert (
        GEMMA4_BASELINE_MODEL_SHA256
        == "5a84cb313260ac447237b890387116dfa8682e49a6b44bc585ae8353abbff18d"
    )
    assert (
        GEMMA4_BASELINE_TOKENIZER_SHA256
        == "cc8d3a0ce36466ccc1278bf987df5f71db1719b9ca6b4118264f45cb627bfe0f"
    )
    assert GEMMA4_BASELINE_ARTIFACT_FORMAT == "HAMOON_GEMMA4_PEFT_SAFETENSORS_V1"
    assert GEMMA4_BASELINE_PIPELINE_VERSION == "gemma4-12b-it-sft-lora-v1"
    assert GEMMA4_CONCRETE_MODEL_ID.endswith(GEMMA4_BASELINE_REVISION)
    assert decode_gemma4_lora_manifest(
        encode_gemma4_lora_manifest(manifest)
    ) == manifest



def _write_fake_base_checkpoint(root: Path) -> tuple[bytes, bytes]:
    model_bytes = b"fake-model-weights"
    tokenizer_bytes = b"fake-tokenizer"
    (root / "model.safetensors").write_bytes(model_bytes)
    (root / "tokenizer.json").write_bytes(tokenizer_bytes)
    (root / "hamoon-revision.txt").write_text(
        GEMMA4_BASELINE_REVISION,
        encoding="utf-8",
    )
    (root / "chat_template.jinja").write_text(
        "{{ messages }}",
        encoding="utf-8",
    )
    (root / "config.json").write_text(
        """{
          "architectures": ["Gemma4UnifiedForConditionalGeneration"],
          "model_type": "gemma4_unified",
          "text_config": {
            "model_type": "gemma4_unified_text",
            "hidden_size": 3840,
            "num_hidden_layers": 48,
            "vocab_size": 262144
          }
        }""",
        encoding="utf-8",
    )
    (root / "processor_config.json").write_text(
        '{"processor_class":"Gemma4UnifiedProcessor"}',
        encoding="utf-8",
    )
    (root / "tokenizer_config.json").write_text(
        (
            '{"processor_class":"Gemma4UnifiedProcessor",'
            '"tokenizer_class":"GemmaTokenizer"}'
        ),
        encoding="utf-8",
    )
    (root / "generation_config.json").write_text(
        (
            '{"bos_token_id":2,"pad_token_id":0,'
            '"eos_token_id":[1,106,50],'
            '"suppress_tokens":[258883,258882]}'
        ),
        encoding="utf-8",
    )
    return model_bytes, tokenizer_bytes


def test_gemma4_base_checkpoint_attests_tokenizer_template_and_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_bytes, tokenizer_bytes = _write_fake_base_checkpoint(tmp_path)
    monkeypatch.setattr(
        gemma4_runtime_module,
        "GEMMA4_BASELINE_MODEL_SHA256",
        hashlib.sha256(model_bytes).hexdigest(),
    )
    monkeypatch.setattr(
        gemma4_runtime_module,
        "GEMMA4_BASELINE_TOKENIZER_SHA256",
        hashlib.sha256(tokenizer_bytes).hexdigest(),
    )

    assert Gemma4BaseCheckpoint(tmp_path).validate() == tmp_path

    (tmp_path / "chat_template.jinja").unlink()
    with pytest.raises(
        Gemma4RuntimeError,
        match="GEMMA4_BASE_CHECKPOINT_FILES_MISSING",
    ):
        Gemma4BaseCheckpoint(tmp_path).validate()


def test_gemma4_base_checkpoint_rejects_tokenizer_or_metadata_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_bytes, tokenizer_bytes = _write_fake_base_checkpoint(tmp_path)
    monkeypatch.setattr(
        gemma4_runtime_module,
        "GEMMA4_BASELINE_MODEL_SHA256",
        hashlib.sha256(model_bytes).hexdigest(),
    )
    monkeypatch.setattr(
        gemma4_runtime_module,
        "GEMMA4_BASELINE_TOKENIZER_SHA256",
        hashlib.sha256(tokenizer_bytes).hexdigest(),
    )

    (tmp_path / "tokenizer.json").write_bytes(b"tampered-tokenizer")
    with pytest.raises(
        Gemma4RuntimeError,
        match="GEMMA4_BASE_CHECKPOINT_TOKENIZER_DIGEST_MISMATCH",
    ):
        Gemma4BaseCheckpoint(tmp_path).validate()

    (tmp_path / "tokenizer.json").write_bytes(tokenizer_bytes)
    (tmp_path / "config.json").write_text(
        '{"architectures":["OtherModel"],"model_type":"other","text_config":{}}',
        encoding="utf-8",
    )
    with pytest.raises(
        Gemma4RuntimeError,
        match="GEMMA4_BASE_CHECKPOINT_MODEL_METADATA_MISMATCH",
    ):
        Gemma4BaseCheckpoint(tmp_path).validate()


def test_gemma4_training_config_has_no_implicit_hyperparameter_defaults() -> None:
    config = Gemma4LoRATrainingConfig.from_json(_training_config())

    assert config.lora_r == 16
    assert config.training_arguments["learning_rate"] == 0.0001

    with pytest.raises(
        Gemma4RuntimeError,
        match="GEMMA4_TRAINING_CONFIGURATION_REQUIRED",
    ):
        Gemma4LoRATrainingConfig.from_json(None)

    with pytest.raises(
        Gemma4RuntimeError,
        match="GEMMA4_TRAINING_CONFIGURATION_FIELDS_INVALID",
    ):
        Gemma4LoRATrainingConfig.from_json('{"lora_r": 16}')


def test_gemma4_training_fails_closed_without_supervised_target_tokens() -> None:
    _require_supervised_target(sequence_length=8, prompt_length=7)

    with pytest.raises(
        Gemma4RuntimeError,
        match="GEMMA4_TRAINING_TARGET_TRUNCATED",
    ):
        _require_supervised_target(sequence_length=8, prompt_length=8)


def test_gemma4_generation_config_requires_explicit_output_bound() -> None:
    config = Gemma4GenerationConfig.from_json(
        '{"max_new_tokens":512,"do_sample":false}'
    )
    assert config.generation_kwargs["max_new_tokens"] == 512

    with pytest.raises(
        Gemma4RuntimeError,
        match="GEMMA4_GENERATION_MAX_NEW_TOKENS_REQUIRED",
    ):
        Gemma4GenerationConfig.from_json('{"do_sample":false}')


def test_gemma4_adapter_artifact_is_deterministic_safetensors_bundle(
    tmp_path: Path,
) -> None:
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir()
    (adapter_dir / "adapter_config.json").write_text(
        '{"peft_type":"LORA"}',
        encoding="utf-8",
    )
    (adapter_dir / "adapter_model.safetensors").write_bytes(b"safe-weights")
    config = Gemma4LoRATrainingConfig.from_json(_training_config())
    manifest = build_gemma4_lora_manifest(
        task_class=AITaskClass.OUTCOME_INTERPRETATION,
        training_dataset_version_id=DATASET_ID,
        training_dataset_manifest_digest="b" * 64,
        training_config_sha256=canonical_training_config_digest(
            config.canonical_dict()
        ),
    )

    first = _build_adapter_artifact(
        adapter_dir=adapter_dir,
        manifest=manifest,
    )
    second = _build_adapter_artifact(
        adapter_dir=adapter_dir,
        manifest=manifest,
    )
    assert first == second
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()

    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    extracted = _extract_adapter_artifact(
        artifact=first,
        destination=extracted_dir,
    )
    assert extracted == manifest
    assert (
        extracted_dir / "adapter_model.safetensors"
    ).read_bytes() == b"safe-weights"


def test_gemma4_runtime_uses_official_multimodal_loader() -> None:
    runtime = Path(
        "src/hamoon/infrastructure/ai/gemma4_runtime.py"
    ).read_text(encoding="utf-8")
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "AutoModelForMultimodalLM.from_pretrained" in runtime
    assert "AutoModelForCausalLM.from_pretrained" not in runtime
    assert "requirements/internal-ai-gemma4.txt" in dockerfile
    assert "uv pip install" in dockerfile
