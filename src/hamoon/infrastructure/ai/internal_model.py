from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Protocol
from uuid import UUID

from pydantic import JsonValue

from hamoon.domains.intelligence.domain.registry import (
    INTERNAL_MODEL_PROVIDER_CODE,
)
from hamoon.infrastructure.ai.contracts import (
    AITaskClass,
    ProviderStructuredRequest,
    ProviderStructuredResponse,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class InternalModelRuntimeError(RuntimeError):
    """The configured in-process internal model runtime cannot execute safely."""


@dataclass(frozen=True, slots=True)
class InternalTrainingExample:
    input_payload: dict[str, JsonValue]
    target_payload: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class InternalTrainingRequest:
    task_class: AITaskClass
    dataset_version_id: UUID
    dataset_manifest_digest: str
    training_pipeline_version: str
    examples: tuple[InternalTrainingExample, ...]
    parent_artifact_sha256: str | None = None
    parent_artifact: bytes | None = None


@dataclass(frozen=True, slots=True)
class StoredInternalModelArtifact:
    artifact_sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class InternalTrainingResult:
    task_class: AITaskClass
    dataset_version_id: UUID
    dataset_manifest_digest: str
    training_pipeline_version: str
    artifact_sha256: str
    artifact_size_bytes: int


class InternalModelArtifactStore(Protocol):
    async def put(
        self,
        *,
        artifact_sha256: str,
        content: bytes,
    ) -> StoredInternalModelArtifact: ...

    async def read(
        self,
        *,
        artifact_sha256: str,
    ) -> bytes: ...


class InternalModelTrainer(Protocol):
    pipeline_version: str

    async def train(
        self,
        request: InternalTrainingRequest,
    ) -> bytes: ...


class InternalModelExecutor(Protocol):
    model_id: str

    async def execute(
        self,
        *,
        artifact: bytes,
        request: ProviderStructuredRequest,
    ) -> dict[str, JsonValue]: ...


class InternalTrainingEngine:
    def __init__(
        self,
        *,
        artifact_store: InternalModelArtifactStore,
        trainers: Mapping[str, InternalModelTrainer],
    ) -> None:
        self._artifact_store = artifact_store
        self._trainers = trainers

    async def train(
        self,
        request: InternalTrainingRequest,
    ) -> InternalTrainingResult:
        dataset_digest = request.dataset_manifest_digest.strip().lower()
        pipeline_version = request.training_pipeline_version.strip()
        if _SHA256_RE.fullmatch(dataset_digest) is None:
            raise InternalModelRuntimeError(
                "TRAINING_DATASET_MANIFEST_DIGEST_INVALID"
            )
        if not pipeline_version:
            raise InternalModelRuntimeError(
                "TRAINING_PIPELINE_VERSION_REQUIRED"
            )
        if not request.examples:
            raise InternalModelRuntimeError("TRAINING_DATASET_EMPTY")
        if (
            request.parent_artifact_sha256 is not None
            and _SHA256_RE.fullmatch(
                request.parent_artifact_sha256.strip().lower()
            )
            is None
        ):
            raise InternalModelRuntimeError(
                "PARENT_MODEL_ARTIFACT_DIGEST_INVALID"
            )

        effective_request = request
        if request.parent_artifact_sha256 is not None:
            parent_digest = request.parent_artifact_sha256.strip().lower()
            parent_artifact = await self._artifact_store.read(
                artifact_sha256=parent_digest,
            )
            if hashlib.sha256(parent_artifact).hexdigest() != parent_digest:
                raise InternalModelRuntimeError(
                    "PARENT_MODEL_ARTIFACT_DIGEST_MISMATCH"
                )
            effective_request = replace(
                request,
                parent_artifact=parent_artifact,
            )

        trainer = self._trainers.get(pipeline_version)
        if trainer is None or trainer.pipeline_version != pipeline_version:
            raise InternalModelRuntimeError(
                "INTERNAL_TRAINER_NOT_REGISTERED"
            )

        artifact = await trainer.train(effective_request)
        if not artifact:
            raise InternalModelRuntimeError("INTERNAL_TRAINER_EMPTY_ARTIFACT")

        digest = hashlib.sha256(artifact).hexdigest()
        stored = await self._artifact_store.put(
            artifact_sha256=digest,
            content=artifact,
        )
        if (
            stored.artifact_sha256 != digest
            or stored.size_bytes != len(artifact)
        ):
            raise InternalModelRuntimeError(
                "INTERNAL_MODEL_ARTIFACT_STORE_ATTESTATION_MISMATCH"
            )

        return InternalTrainingResult(
            task_class=request.task_class,
            dataset_version_id=request.dataset_version_id,
            dataset_manifest_digest=dataset_digest,
            training_pipeline_version=pipeline_version,
            artifact_sha256=digest,
            artifact_size_bytes=len(artifact),
        )


class InternalModelProviderAdapter:
    code = INTERNAL_MODEL_PROVIDER_CODE

    def __init__(
        self,
        *,
        artifact_store: InternalModelArtifactStore,
        executors: Mapping[str, InternalModelExecutor],
    ) -> None:
        self._artifact_store = artifact_store
        self._executors = executors

    async def generate_structured(
        self,
        request: ProviderStructuredRequest,
    ) -> ProviderStructuredResponse:
        digest = (
            request.model_artifact_sha256.strip().lower()
            if request.model_artifact_sha256 is not None
            else ""
        )
        if _SHA256_RE.fullmatch(digest) is None:
            raise InternalModelRuntimeError(
                "INTERNAL_MODEL_ARTIFACT_DIGEST_REQUIRED"
            )

        executor = self._executors.get(request.model_id)
        if executor is None or executor.model_id != request.model_id:
            raise InternalModelRuntimeError(
                "INTERNAL_MODEL_EXECUTOR_NOT_REGISTERED"
            )

        artifact = await self._artifact_store.read(
            artifact_sha256=digest,
        )
        if hashlib.sha256(artifact).hexdigest() != digest:
            raise InternalModelRuntimeError(
                "INTERNAL_MODEL_ARTIFACT_DIGEST_MISMATCH"
            )

        output = await executor.execute(
            artifact=artifact,
            request=request,
        )
        return ProviderStructuredResponse(
            provider_code=self.code,
            model_id=request.model_id,
            output=output,
            model_artifact_sha256=digest,
        )


@dataclass(frozen=True, slots=True)
class InternalModelRuntime:
    artifact_store: InternalModelArtifactStore
    trainers: Mapping[str, InternalModelTrainer]
    executors: Mapping[str, InternalModelExecutor]

    def training_engine(self) -> InternalTrainingEngine:
        return InternalTrainingEngine(
            artifact_store=self.artifact_store,
            trainers=self.trainers,
        )

    def provider_adapter(self) -> InternalModelProviderAdapter:
        return InternalModelProviderAdapter(
            artifact_store=self.artifact_store,
            executors=self.executors,
        )


_runtime: InternalModelRuntime | None = None


def configure_internal_model_runtime(
    *,
    artifact_store: InternalModelArtifactStore,
    trainers: Mapping[str, InternalModelTrainer],
    executors: Mapping[str, InternalModelExecutor],
) -> None:
    global _runtime
    _runtime = InternalModelRuntime(
        artifact_store=artifact_store,
        trainers=dict(trainers),
        executors=dict(executors),
    )


def get_internal_model_runtime() -> InternalModelRuntime | None:
    return _runtime


def reset_internal_model_runtime_for_testing() -> None:
    global _runtime
    _runtime = None
