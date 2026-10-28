"""Offline, local-only Qwen3.5 runner for dataset evaluation.

This deliberately does not implement the production InternalModelExecutor:
Hamoon production inference requires a trained, evaluated, promoted artifact.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import re
import threading
from pathlib import Path
from typing import Any, cast

from jsonschema import ValidationError, validate
from pydantic import JsonValue

from hamoon.infrastructure.ai.contracts import ProviderStructuredRequest

QWEN35_MODEL_ID = "Qwen/Qwen3.5-9B"
QWEN35_BASELINE_REVISION = "c202236235762e1c871ad0ccb60c8ee5ba337b9a"
_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")


class Qwen35RuntimeError(RuntimeError):
    """Local Qwen evaluation failed closed."""


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Qwen35OfflineRunner:
    """Run structured draft generation from an attested local checkpoint."""

    def __init__(
        self,
        *,
        checkpoint_root: Path,
        revision: str,
        manifest_sha256: str,
        max_new_tokens: int = 512,
    ) -> None:
        self._root = checkpoint_root
        self._revision = revision.strip().lower()
        if _REVISION_RE.fullmatch(self._revision) is None:
            raise Qwen35RuntimeError("QWEN35_REVISION_MUST_BE_PINNED")
        if self._revision != QWEN35_BASELINE_REVISION:
            raise Qwen35RuntimeError("QWEN35_REVISION_NOT_APPROVED")
        self._manifest_sha256 = manifest_sha256.strip().lower()
        if re.fullmatch(r"[0-9a-f]{64}", self._manifest_sha256) is None:
            raise Qwen35RuntimeError("QWEN35_MANIFEST_DIGEST_REQUIRED")
        if not 1 <= max_new_tokens <= 2048:
            raise Qwen35RuntimeError("QWEN35_MAX_NEW_TOKENS_OUT_OF_RANGE")
        self._max_new_tokens = max_new_tokens
        self._processor: Any | None = None
        self._model: Any | None = None
        self._load_lock = threading.Lock()

    def _validate_checkpoint(self) -> Path:
        if not self._root.is_dir():
            raise Qwen35RuntimeError("QWEN35_CHECKPOINT_NOT_FOUND")
        revision_file = self._root / "hamoon-revision.txt"
        if not revision_file.is_file():
            raise Qwen35RuntimeError("QWEN35_CHECKPOINT_REVISION_MISSING")
        if (
            revision_file.read_text(encoding="utf-8").strip().lower()
            != self._revision
        ):
            raise Qwen35RuntimeError("QWEN35_CHECKPOINT_REVISION_MISMATCH")
        manifest_path = self._root / "hamoon-checkpoint-manifest.json"
        if not manifest_path.is_file():
            raise Qwen35RuntimeError("QWEN35_CHECKPOINT_MANIFEST_MISSING")
        manifest_bytes = manifest_path.read_bytes()
        if (
            hashlib.sha256(manifest_bytes).hexdigest()
            != self._manifest_sha256
        ):
            raise Qwen35RuntimeError("QWEN35_CHECKPOINT_MANIFEST_DIGEST_MISMATCH")
        try:
            manifest_value = cast(object, json.loads(manifest_bytes))
            if not isinstance(manifest_value, dict):
                raise ValueError
            manifest = cast(dict[str, object], manifest_value)
            files_value = manifest.get("files")
            if (
                manifest.get("model_id") != QWEN35_MODEL_ID
                or manifest.get("revision") != self._revision
                or not isinstance(files_value, dict)
                or not files_value
            ):
                raise ValueError
            declared_files = cast(dict[str, object], files_value)
            verified_files: set[str] = set()
            for relative_name, expected_digest in declared_files.items():
                relative = Path(relative_name)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError
                file_path = self._root / relative
                if (
                    not file_path.is_file()
                    or file_path.is_symlink()
                    or not isinstance(expected_digest, str)
                    or re.fullmatch(r"[0-9a-f]{64}", expected_digest) is None
                ):
                    raise ValueError
                actual_digest = _sha256_file(file_path)
                if actual_digest != expected_digest:
                    raise ValueError
                verified_files.add(relative.as_posix())
            actual_files = {
                file_path.relative_to(self._root).as_posix()
                for file_path in self._root.rglob("*")
                if file_path.is_file()
                and file_path.name not in {
                    "hamoon-checkpoint-manifest.json",
                    "hamoon-revision.txt",
                }
            }
            if actual_files != verified_files:
                raise ValueError
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:
            raise Qwen35RuntimeError("QWEN35_CHECKPOINT_MANIFEST_INVALID") from exc
        config_file = self._root / "config.json"
        processor_file = self._root / "preprocessor_config.json"
        tokenizer_file = self._root / "tokenizer_config.json"
        if not all(
            path.is_file()
            for path in (config_file, processor_file, tokenizer_file)
        ):
            raise Qwen35RuntimeError("QWEN35_CHECKPOINT_FILES_MISSING")
        try:
            config_value = cast(
                object,
                json.loads(config_file.read_text(encoding="utf-8")),
            )
            if not isinstance(config_value, dict):
                raise ValueError
            config = cast(dict[str, object], config_value)
            architecture = config.get("architectures")
            model_type = config.get("model_type")
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:
            raise Qwen35RuntimeError("QWEN35_CHECKPOINT_METADATA_INVALID") from exc
        if (
            architecture != ["Qwen3_5ForConditionalGeneration"]
            or model_type != "qwen3_5"
        ):
            raise Qwen35RuntimeError("QWEN35_CHECKPOINT_MODEL_MISMATCH")
        return self._root

    def _load(self) -> tuple[Any, Any]:
        with self._load_lock:
            if self._processor is not None and self._model is not None:
                return self._processor, self._model
            root = self._validate_checkpoint()
            try:
                transformers = importlib.import_module("transformers")
            except ModuleNotFoundError as exc:
                raise Qwen35RuntimeError("QWEN35_TRANSFORMERS_MISSING") from exc
            try:
                processor = transformers.AutoProcessor.from_pretrained(
                    str(root),
                    local_files_only=True,
                    trust_remote_code=False,
                )
                model = transformers.AutoModelForMultimodalLM.from_pretrained(
                    str(root),
                    local_files_only=True,
                    trust_remote_code=False,
                    dtype="auto",
                    device_map="auto",
                )
            except Exception as exc:
                raise Qwen35RuntimeError("QWEN35_LOCAL_MODEL_LOAD_FAILED") from exc
            model.eval()
            self._processor, self._model = processor, model
            return processor, model

    async def generate_structured(
        self,
        request: ProviderStructuredRequest,
    ) -> dict[str, JsonValue]:
        return await asyncio.to_thread(self._generate_sync, request)

    def _generate_sync(
        self,
        request: ProviderStructuredRequest,
    ) -> dict[str, JsonValue]:
        processor, model = self._load()
        system_content = "\n".join(
            part
            for part in (
                "You are Hamoon's offline evaluation assistant. Draft only. "
                "A human must review every suggestion.",
                "Never calculate or alter PGOR, infer missing facts, or make "
                "diagnosis, prescription, provider, eligibility, or outcome decisions.",
                request.instructions.strip(),
                "Return exactly one JSON object matching this JSON Schema:",
                _canonical_json(request.output_schema),
            )
            if part
        )
        messages = [
            {"role": "system", "content": system_content},
            {
                "role": "user",
                "content": _canonical_json(
                    {
                        "task_class": request.task_class.value,
                        "feature_schema_version": request.feature_schema_version,
                        "features": request.features,
                    }
                ),
            },
        ]
        try:
            inputs = processor.apply_chat_template(
                messages,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
                add_generation_prompt=True,
            ).to(model.device)
            input_length = int(inputs["input_ids"].shape[-1])
            torch = importlib.import_module("torch")
            with torch.inference_mode():
                output_ids = model.generate(
                    **inputs,
                    max_new_tokens=self._max_new_tokens,
                    do_sample=False,
                )
            text = processor.decode(
                output_ids[0][input_length:], skip_special_tokens=True
            ).strip()
            parsed = cast(object, json.loads(text))
        except json.JSONDecodeError:
            raise Qwen35RuntimeError("QWEN35_OUTPUT_INVALID") from None
        except Qwen35RuntimeError:
            raise
        except Exception as exc:
            raise Qwen35RuntimeError("QWEN35_GENERATION_FAILED") from exc
        if not isinstance(parsed, dict):
            raise Qwen35RuntimeError("QWEN35_OUTPUT_OBJECT_REQUIRED")
        try:
            validate(instance=parsed, schema=request.output_schema)
        except ValidationError as exc:
            raise Qwen35RuntimeError("QWEN35_OUTPUT_SCHEMA_INVALID") from exc
        return cast(dict[str, JsonValue], parsed)
