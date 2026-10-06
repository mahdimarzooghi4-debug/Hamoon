from __future__ import annotations

import asyncio
import hashlib
import importlib
import io
import json
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from pydantic import JsonValue

from hamoon.infrastructure.ai.contracts import (
    AITaskClass,
    ProviderStructuredRequest,
)
from hamoon.infrastructure.ai.gemma4_baseline import (
    GEMMA4_BASELINE_MODEL_SHA256,
    GEMMA4_BASELINE_PIPELINE_VERSION,
    GEMMA4_BASELINE_REVISION,
    GEMMA4_CONCRETE_MODEL_ID,
    Gemma4LoRAArtifactManifest,
    build_gemma4_lora_manifest,
    canonical_training_config_digest,
    decode_gemma4_lora_manifest,
    encode_gemma4_lora_manifest,
)
from hamoon.infrastructure.ai.internal_model import (
    InternalModelExecutor,
    InternalModelRuntimeError,
    InternalModelTrainer,
    InternalTrainingExample,
    InternalTrainingRequest,
)


_REQUIRED_BASE_FILES = (
    "config.json",
    "generation_config.json",
    "model.safetensors",
    "processor_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
)
_REQUIRED_ADAPTER_FILES = (
    "adapter_config.json",
    "adapter_model.safetensors",
)


class Gemma4RuntimeError(InternalModelRuntimeError):
    """Gemma 4 local training or inference failed closed."""


@dataclass(frozen=True, slots=True)
class Gemma4LoRATrainingConfig:
    max_sequence_length: int
    dtype: str
    device_map: str
    lora_r: int
    lora_alpha: int
    lora_dropout: float
    lora_bias: str
    target_modules: tuple[str, ...]
    training_arguments: dict[str, JsonValue]

    @classmethod
    def from_json(cls, raw: str | None) -> Gemma4LoRATrainingConfig:
        if raw is None or not raw.strip():
            raise Gemma4RuntimeError(
                "GEMMA4_TRAINING_CONFIGURATION_REQUIRED"
            )
        try:
            value = cast(object, json.loads(raw))
        except json.JSONDecodeError as exc:
            raise Gemma4RuntimeError(
                "GEMMA4_TRAINING_CONFIGURATION_INVALID"
            ) from exc
        if not isinstance(value, dict):
            raise Gemma4RuntimeError(
                "GEMMA4_TRAINING_CONFIGURATION_INVALID"
            )
        data = cast(dict[str, object], value)
        required = {
            "max_sequence_length",
            "dtype",
            "device_map",
            "lora_r",
            "lora_alpha",
            "lora_dropout",
            "lora_bias",
            "target_modules",
            "training_arguments",
        }
        if set(data) != required:
            raise Gemma4RuntimeError(
                "GEMMA4_TRAINING_CONFIGURATION_FIELDS_INVALID"
            )

        max_sequence_length = data["max_sequence_length"]
        lora_r = data["lora_r"]
        lora_alpha = data["lora_alpha"]
        lora_dropout = data["lora_dropout"]
        target_modules = data["target_modules"]
        training_arguments = data["training_arguments"]
        if (
            not isinstance(max_sequence_length, int)
            or isinstance(max_sequence_length, bool)
            or max_sequence_length <= 0
            or not isinstance(lora_r, int)
            or isinstance(lora_r, bool)
            or lora_r <= 0
            or not isinstance(lora_alpha, int)
            or isinstance(lora_alpha, bool)
            or lora_alpha <= 0
            or not isinstance(lora_dropout, (int, float))
            or isinstance(lora_dropout, bool)
            or not 0 <= float(lora_dropout) < 1
            or not isinstance(target_modules, list)
            or not target_modules
            or not all(
                isinstance(item, str) and item.strip()
                for item in target_modules
            )
            or not isinstance(training_arguments, dict)
        ):
            raise Gemma4RuntimeError(
                "GEMMA4_TRAINING_CONFIGURATION_INVALID"
            )

        dtype = str(data["dtype"]).strip()
        device_map = str(data["device_map"]).strip()
        lora_bias = str(data["lora_bias"]).strip()
        if dtype not in {"float16", "bfloat16", "float32"}:
            raise Gemma4RuntimeError("GEMMA4_TRAINING_DTYPE_INVALID")
        if not device_map:
            raise Gemma4RuntimeError("GEMMA4_DEVICE_MAP_REQUIRED")
        if lora_bias not in {"none", "all", "lora_only"}:
            raise Gemma4RuntimeError("GEMMA4_LORA_BIAS_INVALID")

        required_training_args = {
            "learning_rate",
            "num_train_epochs",
            "per_device_train_batch_size",
            "gradient_accumulation_steps",
            "weight_decay",
            "warmup_ratio",
            "lr_scheduler_type",
            "optim",
            "max_grad_norm",
            "seed",
            "gradient_checkpointing",
        }
        if set(training_arguments) != required_training_args:
            raise Gemma4RuntimeError(
                "GEMMA4_TRAINING_ARGUMENTS_FIELDS_INVALID"
            )
        normalized_args = cast(dict[str, JsonValue], dict(training_arguments))
        return cls(
            max_sequence_length=max_sequence_length,
            dtype=dtype,
            device_map=device_map,
            lora_r=lora_r,
            lora_alpha=lora_alpha,
            lora_dropout=float(lora_dropout),
            lora_bias=lora_bias,
            target_modules=tuple(
                cast(str, item).strip()
                for item in target_modules
            ),
            training_arguments=normalized_args,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "max_sequence_length": self.max_sequence_length,
            "dtype": self.dtype,
            "device_map": self.device_map,
            "lora_r": self.lora_r,
            "lora_alpha": self.lora_alpha,
            "lora_dropout": self.lora_dropout,
            "lora_bias": self.lora_bias,
            "target_modules": list(self.target_modules),
            "training_arguments": self.training_arguments,
        }


@dataclass(frozen=True, slots=True)
class Gemma4GenerationConfig:
    generation_kwargs: dict[str, JsonValue]

    @classmethod
    def from_json(cls, raw: str | None) -> Gemma4GenerationConfig:
        if raw is None or not raw.strip():
            raise Gemma4RuntimeError(
                "GEMMA4_GENERATION_CONFIGURATION_REQUIRED"
            )
        try:
            value = cast(object, json.loads(raw))
        except json.JSONDecodeError as exc:
            raise Gemma4RuntimeError(
                "GEMMA4_GENERATION_CONFIGURATION_INVALID"
            ) from exc
        if not isinstance(value, dict):
            raise Gemma4RuntimeError(
                "GEMMA4_GENERATION_CONFIGURATION_INVALID"
            )
        data = cast(dict[str, object], value)
        forbidden = {
            "assistant_model",
            "streamer",
            "synced_gpus",
            "tokenizer",
        }
        if forbidden.intersection(data):
            raise Gemma4RuntimeError(
                "GEMMA4_GENERATION_CONFIGURATION_FORBIDDEN_FIELD"
            )
        max_new_tokens = data.get("max_new_tokens")
        if (
            not isinstance(max_new_tokens, int)
            or isinstance(max_new_tokens, bool)
            or max_new_tokens <= 0
        ):
            raise Gemma4RuntimeError(
                "GEMMA4_GENERATION_MAX_NEW_TOKENS_REQUIRED"
            )
        return cls(
            generation_kwargs=cast(dict[str, JsonValue], dict(data))
        )


class Gemma4BaseCheckpoint:
    def __init__(self, root: Path | None) -> None:
        self._root = root
        self._validated = False
        self._lock = threading.Lock()

    @property
    def root(self) -> Path:
        if self._root is None:
            raise Gemma4RuntimeError(
                "GEMMA4_BASE_CHECKPOINT_NOT_CONFIGURED"
            )
        return self._root

    def validate(self) -> Path:
        with self._lock:
            if self._validated:
                return self.root
            root = self.root
            if not root.is_dir():
                raise Gemma4RuntimeError(
                    "GEMMA4_BASE_CHECKPOINT_NOT_FOUND"
                )
            missing = [
                name
                for name in _REQUIRED_BASE_FILES
                if not (root / name).is_file()
            ]
            if missing:
                raise Gemma4RuntimeError(
                    "GEMMA4_BASE_CHECKPOINT_FILES_MISSING"
                )
            revision_path = root / "hamoon-revision.txt"
            if (
                not revision_path.is_file()
                or revision_path.read_text(encoding="utf-8").strip()
                != GEMMA4_BASELINE_REVISION
            ):
                raise Gemma4RuntimeError(
                    "GEMMA4_BASE_CHECKPOINT_REVISION_MISMATCH"
                )

            digest = hashlib.sha256()
            with (root / "model.safetensors").open("rb") as handle:
                for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != GEMMA4_BASELINE_MODEL_SHA256:
                raise Gemma4RuntimeError(
                    "GEMMA4_BASE_CHECKPOINT_DIGEST_MISMATCH"
                )
            self._validated = True
            return root


def _ml_stack() -> tuple[Any, Any, Any]:
    try:
        torch = importlib.import_module("torch")
        transformers = importlib.import_module("transformers")
        peft = importlib.import_module("peft")
    except ModuleNotFoundError as exc:
        raise Gemma4RuntimeError(
            "GEMMA4_RUNTIME_DEPENDENCY_MISSING"
        ) from exc
    return torch, transformers, peft


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _training_messages(
    *,
    task_class: AITaskClass,
    example: InternalTrainingExample,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Hamoon governed structured-learning example. "
                f"Task class: {task_class.value}. "
                "Return only the final JSON object."
            ),
        },
        {
            "role": "user",
            "content": _canonical_json(example.input_payload),
        },
        {
            "role": "assistant",
            "content": _canonical_json(example.target_payload),
        },
    ]


def _zip_entry(name: str, content: bytes) -> tuple[zipfile.ZipInfo, bytes]:
    info = zipfile.ZipInfo(
        filename=name,
        date_time=(1980, 1, 1, 0, 0, 0),
    )
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o600 << 16
    return info, content


def _build_adapter_artifact(
    *,
    adapter_dir: Path,
    manifest: Gemma4LoRAArtifactManifest,
) -> bytes:
    files: dict[str, bytes] = {
        "manifest.json": encode_gemma4_lora_manifest(manifest),
    }
    for name in _REQUIRED_ADAPTER_FILES:
        path = adapter_dir / name
        if not path.is_file():
            raise Gemma4RuntimeError(
                "GEMMA4_ADAPTER_ARTIFACT_FILE_MISSING"
            )
        files[name] = path.read_bytes()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        for name in sorted(files):
            info, content = _zip_entry(name, files[name])
            archive.writestr(info, content)
    return buffer.getvalue()


def _extract_adapter_artifact(
    *,
    artifact: bytes,
    destination: Path,
) -> Gemma4LoRAArtifactManifest:
    try:
        with zipfile.ZipFile(io.BytesIO(artifact), mode="r") as archive:
            names = tuple(sorted(archive.namelist()))
            expected = tuple(
                sorted(("manifest.json", *_REQUIRED_ADAPTER_FILES))
            )
            if names != expected:
                raise Gemma4RuntimeError(
                    "GEMMA4_ADAPTER_ARTIFACT_FILES_INVALID"
                )
            manifest = decode_gemma4_lora_manifest(
                archive.read("manifest.json")
            )
            for name in _REQUIRED_ADAPTER_FILES:
                (destination / name).write_bytes(archive.read(name))
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise Gemma4RuntimeError(
            "GEMMA4_ADAPTER_ARTIFACT_INVALID"
        ) from exc
    return manifest


class Gemma4LoRATrainer(InternalModelTrainer):
    pipeline_version = GEMMA4_BASELINE_PIPELINE_VERSION
    model_id = GEMMA4_CONCRETE_MODEL_ID

    def __init__(
        self,
        *,
        base_checkpoint_root: Path | None,
        training_config_json: str | None,
    ) -> None:
        self._checkpoint = Gemma4BaseCheckpoint(base_checkpoint_root)
        self._training_config_json = training_config_json

    async def train(self, request: InternalTrainingRequest) -> bytes:
        if request.training_pipeline_version != self.pipeline_version:
            raise Gemma4RuntimeError("GEMMA4_TRAINING_PIPELINE_MISMATCH")
        return await asyncio.to_thread(self._train_sync, request)

    def _train_sync(self, request: InternalTrainingRequest) -> bytes:
        config = Gemma4LoRATrainingConfig.from_json(
            self._training_config_json
        )
        root = self._checkpoint.validate()
        torch, transformers, peft = _ml_stack()
        dtype = getattr(torch, config.dtype)

        processor = transformers.AutoProcessor.from_pretrained(
            str(root),
            local_files_only=True,
        )
        model = transformers.AutoModelForCausalLM.from_pretrained(
            str(root),
            local_files_only=True,
            dtype=dtype,
            device_map=config.device_map,
        )
        model.config.use_cache = False

        parent_tmp: TemporaryDirectory[str] | None = None
        try:
            if request.parent_artifact is not None:
                parent_tmp = TemporaryDirectory(
                    prefix="hamoon-gemma4-parent-"
                )
                parent_dir = Path(parent_tmp.name)
                parent_manifest = _extract_adapter_artifact(
                    artifact=request.parent_artifact,
                    destination=parent_dir,
                )
                if parent_manifest.task_class != request.task_class.value:
                    raise Gemma4RuntimeError(
                        "GEMMA4_PARENT_ARTIFACT_TASK_CLASS_MISMATCH"
                    )
                model = peft.PeftModel.from_pretrained(
                    model,
                    str(parent_dir),
                    is_trainable=True,
                )
            else:
                lora_config = peft.LoraConfig(
                    r=config.lora_r,
                    lora_alpha=config.lora_alpha,
                    lora_dropout=config.lora_dropout,
                    bias=config.lora_bias,
                    target_modules=list(config.target_modules),
                    task_type=peft.TaskType.CAUSAL_LM,
                )
                model = peft.get_peft_model(model, lora_config)

            encoded_examples = [
                self._encode_example(
                    torch=torch,
                    processor=processor,
                    task_class=request.task_class,
                    example=example,
                    max_sequence_length=config.max_sequence_length,
                )
                for example in request.examples
            ]

            class _Dataset(torch.utils.data.Dataset):  # type: ignore[misc]
                def __len__(self) -> int:
                    return len(encoded_examples)

                def __getitem__(self, index: int) -> dict[str, Any]:
                    return encoded_examples[index]

            with TemporaryDirectory(prefix="hamoon-gemma4-train-") as tmp:
                args = dict(config.training_arguments)
                args.update(
                    {
                        "output_dir": str(Path(tmp) / "trainer-output"),
                        "save_strategy": "no",
                        "logging_strategy": "no",
                        "report_to": [],
                        "remove_unused_columns": False,
                        "bf16": config.dtype == "bfloat16",
                        "fp16": config.dtype == "float16",
                    }
                )
                training_args = transformers.TrainingArguments(**args)
                trainer = transformers.Trainer(
                    model=model,
                    args=training_args,
                    train_dataset=_Dataset(),
                )
                trainer.train()

                adapter_dir = Path(tmp) / "adapter"
                model.save_pretrained(
                    str(adapter_dir),
                    safe_serialization=True,
                )
                training_config_digest = canonical_training_config_digest(
                    config.canonical_dict()
                )
                manifest = build_gemma4_lora_manifest(
                    task_class=request.task_class,
                    training_dataset_version_id=request.dataset_version_id,
                    training_dataset_manifest_digest=(
                        request.dataset_manifest_digest
                    ),
                    training_config_sha256=training_config_digest,
                )
                return _build_adapter_artifact(
                    adapter_dir=adapter_dir,
                    manifest=manifest,
                )
        finally:
            if parent_tmp is not None:
                parent_tmp.cleanup()

    @staticmethod
    def _encode_example(
        *,
        torch: Any,
        processor: Any,
        task_class: AITaskClass,
        example: InternalTrainingExample,
        max_sequence_length: int,
    ) -> dict[str, Any]:
        prompt_messages = _training_messages(
            task_class=task_class,
            example=example,
        )[:-1]
        full_messages = _training_messages(
            task_class=task_class,
            example=example,
        )
        prompt = processor.apply_chat_template(
            prompt_messages,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            add_generation_prompt=True,
            enable_thinking=False,
        )
        full = processor.apply_chat_template(
            full_messages,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            add_generation_prompt=False,
            enable_thinking=False,
        )
        input_ids = full["input_ids"][0][:max_sequence_length]
        attention_mask = full["attention_mask"][0][:max_sequence_length]
        prompt_length = min(
            int(prompt["input_ids"].shape[-1]),
            int(input_ids.shape[-1]),
        )
        labels = input_ids.clone()
        labels[:prompt_length] = -100

        current_length = int(input_ids.shape[-1])
        if current_length < max_sequence_length:
            pad_length = max_sequence_length - current_length
            pad_id = processor.tokenizer.pad_token_id
            if pad_id is None:
                raise Gemma4RuntimeError(
                    "GEMMA4_TOKENIZER_PAD_TOKEN_REQUIRED"
                )
            input_ids = torch.cat(
                (
                    input_ids,
                    torch.full(
                        (pad_length,),
                        int(pad_id),
                        dtype=input_ids.dtype,
                    ),
                )
            )
            attention_mask = torch.cat(
                (
                    attention_mask,
                    torch.zeros(
                        (pad_length,),
                        dtype=attention_mask.dtype,
                    ),
                )
            )
            labels = torch.cat(
                (
                    labels,
                    torch.full(
                        (pad_length,),
                        -100,
                        dtype=labels.dtype,
                    ),
                )
            )
        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }


class Gemma4LoRAExecutor(InternalModelExecutor):
    model_id = GEMMA4_CONCRETE_MODEL_ID

    def __init__(
        self,
        *,
        base_checkpoint_root: Path | None,
        generation_config_json: str | None,
    ) -> None:
        self._checkpoint = Gemma4BaseCheckpoint(base_checkpoint_root)
        self._generation_config_json = generation_config_json
        self._loaded_artifact_sha256: str | None = None
        self._processor: Any | None = None
        self._model: Any | None = None
        self._load_lock = threading.Lock()

    async def execute(
        self,
        *,
        artifact: bytes,
        request: ProviderStructuredRequest,
    ) -> dict[str, JsonValue]:
        return await asyncio.to_thread(
            self._execute_sync,
            artifact,
            request,
        )

    def _execute_sync(
        self,
        artifact: bytes,
        request: ProviderStructuredRequest,
    ) -> dict[str, JsonValue]:
        config = Gemma4GenerationConfig.from_json(
            self._generation_config_json
        )
        digest = hashlib.sha256(artifact).hexdigest()
        processor, model, manifest = self._load(
            artifact=artifact,
            artifact_sha256=digest,
        )
        if manifest.task_class != request.task_class.value:
            raise Gemma4RuntimeError(
                "GEMMA4_ARTIFACT_TASK_CLASS_MISMATCH"
            )

        system_parts = [
            request.instructions.strip(),
            "Return only one JSON object matching this JSON Schema:",
            _canonical_json(request.output_schema),
        ]
        messages = [
            {
                "role": "system",
                "content": "\n".join(
                    part for part in system_parts if part
                ),
            },
            {
                "role": "user",
                "content": _canonical_json(
                    {
                        "feature_schema_version": (
                            request.feature_schema_version
                        ),
                        "features": request.features,
                    }
                ),
            },
        ]
        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            add_generation_prompt=True,
            enable_thinking=False,
        )
        inputs = inputs.to(model.device)
        input_length = int(inputs["input_ids"].shape[-1])
        torch, _transformers, _peft = _ml_stack()
        with torch.inference_mode():
            output_ids = model.generate(
                **inputs,
                **config.generation_kwargs,
            )
        response = processor.decode(
            output_ids[0][input_length:],
            skip_special_tokens=True,
        ).strip()
        try:
            parsed = cast(object, json.loads(response))
        except json.JSONDecodeError as exc:
            raise Gemma4RuntimeError(
                "GEMMA4_OUTPUT_JSON_INVALID"
            ) from exc
        if not isinstance(parsed, dict):
            raise Gemma4RuntimeError(
                "GEMMA4_OUTPUT_JSON_OBJECT_REQUIRED"
            )
        return cast(dict[str, JsonValue], parsed)

    def _load(
        self,
        *,
        artifact: bytes,
        artifact_sha256: str,
    ) -> tuple[Any, Any, Gemma4LoRAArtifactManifest]:
        with self._load_lock:
            if (
                self._loaded_artifact_sha256 == artifact_sha256
                and self._processor is not None
                and self._model is not None
            ):
                with TemporaryDirectory(
                    prefix="hamoon-gemma4-manifest-"
                ) as tmp:
                    manifest = _extract_adapter_artifact(
                        artifact=artifact,
                        destination=Path(tmp),
                    )
                return self._processor, self._model, manifest

            root = self._checkpoint.validate()
            _torch, transformers, peft = _ml_stack()
            with TemporaryDirectory(
                prefix="hamoon-gemma4-adapter-"
            ) as tmp:
                adapter_dir = Path(tmp)
                manifest = _extract_adapter_artifact(
                    artifact=artifact,
                    destination=adapter_dir,
                )
                processor = transformers.AutoProcessor.from_pretrained(
                    str(root),
                    local_files_only=True,
                )
                base_model = transformers.AutoModelForCausalLM.from_pretrained(
                    str(root),
                    local_files_only=True,
                    dtype="auto",
                    device_map="auto",
                )
                model = peft.PeftModel.from_pretrained(
                    base_model,
                    str(adapter_dir),
                    is_trainable=False,
                )
                model.eval()

            self._loaded_artifact_sha256 = artifact_sha256
            self._processor = processor
            self._model = model
            return processor, model, manifest
