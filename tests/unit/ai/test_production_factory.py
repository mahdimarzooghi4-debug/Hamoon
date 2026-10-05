from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from hamoon.app.config.settings import Settings
from hamoon.domains.intelligence.domain.registry import ResolvedAIRoute
from hamoon.infrastructure.ai.contracts import AIRoutingPolicy, AITaskClass
from hamoon.infrastructure.ai.production_factory import (
    LocalAIRuntimeConfigurationError,
    build_local_ai_gateway,
)

ROUTE_ID = UUID("11111111-1111-1111-1111-111111111111")
EVAL_ID = UUID("22222222-2222-2222-2222-222222222222")


def _route(provider_code: str = "HAMOON_LOCAL") -> ResolvedAIRoute:
    return ResolvedAIRoute(
        routing_policy=AIRoutingPolicy(
            id=ROUTE_ID,
            version="route-v1",
            task_class=AITaskClass.DIAGNOSIS,
            provider_code=provider_code,
            model_alias="hamoon.diagnosis.local",
            concrete_model_id="hamoon-diagnosis-local-v1",
            model_artifact_ref="diagnosis/v1",
            model_artifact_sha256="a" * 64,
            prompt_policy_version="diagnosis-prompt-v1",
            output_schema_version="diagnosis-v1",
        ),
        instructions="grounded",
        evaluation_run_id=EVAL_ID,
        evaluation_completed_at=datetime.now(UTC),
    )


def _settings(tmp_path: Path) -> Settings:
    model_root = tmp_path / "models"
    model_root.mkdir()
    runner = tmp_path / "runner"
    runner.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    runner.chmod(0o755)
    return Settings(
        _env_file=None,
        ai_model_root=str(model_root),
        ai_local_runner_path=str(runner),
    )


def test_production_factory_accepts_only_local_model_runtime(
    tmp_path: Path,
) -> None:
    gateway = build_local_ai_gateway(
        settings=_settings(tmp_path),
        route=_route(),
    )

    assert gateway is not None


def test_production_factory_rejects_external_provider(tmp_path: Path) -> None:
    with pytest.raises(
        LocalAIRuntimeConfigurationError,
        match="EXTERNAL_OR_REMOTE_AI_PROVIDER_PRODUCTION_FORBIDDEN",
    ):
        build_local_ai_gateway(
            settings=_settings(tmp_path),
            route=_route("OPENAI"),
        )


def test_production_factory_requires_artifact_identity(tmp_path: Path) -> None:
    route = _route()
    route = ResolvedAIRoute(
        routing_policy=AIRoutingPolicy(
            id=route.routing_policy.id,
            version=route.routing_policy.version,
            task_class=route.routing_policy.task_class,
            provider_code="HAMOON_LOCAL",
            model_alias=route.routing_policy.model_alias,
            concrete_model_id=route.routing_policy.concrete_model_id,
            prompt_policy_version=route.routing_policy.prompt_policy_version,
            output_schema_version=route.routing_policy.output_schema_version,
        ),
        instructions=route.instructions,
        evaluation_run_id=route.evaluation_run_id,
        evaluation_completed_at=route.evaluation_completed_at,
    )

    with pytest.raises(
        LocalAIRuntimeConfigurationError,
        match="LOCAL_MODEL_ARTIFACT_IDENTITY_REQUIRED",
    ):
        build_local_ai_gateway(
            settings=_settings(tmp_path),
            route=route,
        )
