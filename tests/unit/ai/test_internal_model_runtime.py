from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import JsonValue

from hamoon.app.config.settings import Settings
from hamoon.domains.intelligence.domain.registry import ResolvedAIRoute
from hamoon.infrastructure.ai.contracts import (
    AIRoutingPolicy,
    AITaskClass,
    ProviderStructuredRequest,
    StructuredAIRequest,
)
from hamoon.infrastructure.ai.internal_model import (
    InternalModelRuntimeError,
    InternalTrainingEngine,
    InternalTrainingExample,
    InternalTrainingRequest,
    StoredInternalModelArtifact,
    configure_internal_model_runtime,
    reset_internal_model_runtime_for_testing,
)
from hamoon.infrastructure.ai.production_factory import (
    InternalModelRuntimeConfigurationError,
    build_internal_model_gateway,
)


DATASET_ID = UUID("33333333-3333-3333-3333-333333333333")


def _route(*, provider_code: str, digest: str | None) -> ResolvedAIRoute:
    return ResolvedAIRoute(
        routing_policy=AIRoutingPolicy(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            version="route-v1",
            task_class=AITaskClass.DIAGNOSIS,
            provider_code=provider_code,
            model_alias="hamoon.diagnosis",
            concrete_model_id="internal-model-v1",
            model_artifact_sha256=digest,
            prompt_policy_version="prompt-v1",
            output_schema_version="diagnosis-v1",
        ),
        instructions="",
        evaluation_run_id=UUID("22222222-2222-2222-2222-222222222222"),
        evaluation_completed_at=datetime(2026, 10, 6, tzinfo=UTC),
    )


class ArtifactStore:
    def __init__(self) -> None:
        self.items: dict[str, bytes] = {}

    async def put(
        self,
        *,
        artifact_sha256: str,
        content: bytes,
    ) -> StoredInternalModelArtifact:
        existing = self.items.get(artifact_sha256)
        if existing is not None and existing != content:
            raise AssertionError("digest collision")
        self.items[artifact_sha256] = content
        return StoredInternalModelArtifact(
            artifact_sha256=artifact_sha256,
            size_bytes=len(content),
        )

    async def read(self, *, artifact_sha256: str) -> bytes:
        try:
            return self.items[artifact_sha256]
        except KeyError as exc:
            raise LookupError("artifact missing") from exc


class Trainer:
    pipeline_version = "pipeline-v1"

    async def train(self, request: InternalTrainingRequest) -> bytes:
        assert request.dataset_version_id == DATASET_ID
        assert request.task_class is AITaskClass.DIAGNOSIS
        return b"opaque-internal-model-artifact-v1"


class Executor:
    model_id = "internal-model-v1"

    async def execute(
        self,
        *,
        artifact: bytes,
        request: ProviderStructuredRequest,
    ) -> dict[str, JsonValue]:
        assert artifact == b"opaque-internal-model-artifact-v1"
        assert request.task_class is AITaskClass.DIAGNOSIS
        return {
            "schema_version": "test-v1",
            "summary": "internal result",
        }


@pytest.fixture(autouse=True)
def _reset_runtime() -> Iterator[None]:
    reset_internal_model_runtime_for_testing()
    yield
    reset_internal_model_runtime_for_testing()


def test_production_rejects_non_internal_model_provider() -> None:
    with pytest.raises(
        InternalModelRuntimeConfigurationError,
        match="EXTERNAL_AI_PROVIDER_PRODUCTION_FORBIDDEN",
    ):
        build_internal_model_gateway(
            settings=Settings(_env_file=None),
            route=_route(provider_code="EXTERNAL", digest="a" * 64),
        )


def test_internal_model_fails_closed_until_runtime_is_configured() -> None:
    with pytest.raises(
        InternalModelRuntimeConfigurationError,
        match="INTERNAL_MODEL_RUNTIME_NOT_CONFIGURED",
    ):
        build_internal_model_gateway(
            settings=Settings(_env_file=None),
            route=_route(provider_code="INTERNAL_MODEL", digest="b" * 64),
        )


@pytest.mark.asyncio
async def test_training_engine_runs_registered_in_process_trainer_and_stores_artifact() -> None:
    store = ArtifactStore()
    engine = InternalTrainingEngine(
        artifact_store=store,
        trainers={"pipeline-v1": Trainer()},
    )

    result = await engine.train(
        InternalTrainingRequest(
            task_class=AITaskClass.DIAGNOSIS,
            dataset_version_id=DATASET_ID,
            dataset_manifest_digest="a" * 64,
            training_pipeline_version="pipeline-v1",
            examples=(
                InternalTrainingExample(
                    input_payload={"feature": "value"},
                    target_payload={"label": "accepted"},
                ),
            ),
        )
    )

    assert result.dataset_version_id == DATASET_ID
    assert result.training_pipeline_version == "pipeline-v1"
    assert result.artifact_sha256 in store.items
    assert result.artifact_size_bytes == len(store.items[result.artifact_sha256])


@pytest.mark.asyncio
async def test_training_engine_fails_closed_without_registered_trainer() -> None:
    with pytest.raises(
        InternalModelRuntimeError,
        match="INTERNAL_TRAINER_NOT_REGISTERED",
    ):
        await InternalTrainingEngine(
            artifact_store=ArtifactStore(),
            trainers={},
        ).train(
            InternalTrainingRequest(
                task_class=AITaskClass.DIAGNOSIS,
                dataset_version_id=DATASET_ID,
                dataset_manifest_digest="a" * 64,
                training_pipeline_version="pipeline-v1",
                examples=(
                    InternalTrainingExample(
                        input_payload={"feature": "value"},
                        target_payload={"label": "accepted"},
                    ),
                ),
            )
        )


@pytest.mark.asyncio
async def test_production_gateway_executes_registered_internal_model_in_process() -> None:
    store = ArtifactStore()
    training = await InternalTrainingEngine(
        artifact_store=store,
        trainers={"pipeline-v1": Trainer()},
    ).train(
        InternalTrainingRequest(
            task_class=AITaskClass.DIAGNOSIS,
            dataset_version_id=DATASET_ID,
            dataset_manifest_digest="a" * 64,
            training_pipeline_version="pipeline-v1",
            examples=(
                InternalTrainingExample(
                    input_payload={"feature": "value"},
                    target_payload={"label": "accepted"},
                ),
            ),
        )
    )
    configure_internal_model_runtime(
        artifact_store=store,
        trainers={"pipeline-v1": Trainer()},
        executors={"internal-model-v1": Executor()},
    )

    route = _route(
        provider_code="INTERNAL_MODEL",
        digest=training.artifact_sha256,
    )
    gateway = build_internal_model_gateway(
        settings=Settings(_env_file=None),
        route=route,
    )
    result = await gateway.generate_structured(
        request=StructuredAIRequest(
            task_class=AITaskClass.DIAGNOSIS,
            feature_package_id=UUID("44444444-4444-4444-4444-444444444444"),
            feature_schema_version="features-v1",
            features={"feature": "value"},
            correlation_id="corr-1",
        ),
        routing_policy=route.routing_policy,
        output_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["schema_version", "summary"],
            "properties": {
                "schema_version": {"const": "test-v1"},
                "summary": {"type": "string"},
            },
        },
    )

    assert result.provider_code == "INTERNAL_MODEL"
    assert result.model_id == "internal-model-v1"
    assert result.model_artifact_sha256 == training.artifact_sha256
    assert result.output["summary"] == "internal result"
