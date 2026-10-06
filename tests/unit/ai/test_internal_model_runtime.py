from datetime import UTC, datetime
from uuid import UUID

import pytest

from hamoon.app.config.settings import Settings
from hamoon.domains.intelligence.domain.registry import ResolvedAIRoute
from hamoon.infrastructure.ai.contracts import AIRoutingPolicy, AITaskClass
from hamoon.infrastructure.ai.production_factory import (
    InternalModelRuntimeConfigurationError,
    build_internal_model_gateway,
)


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


def test_production_rejects_non_internal_model_provider() -> None:
    with pytest.raises(
        InternalModelRuntimeConfigurationError,
        match="EXTERNAL_AI_PROVIDER_PRODUCTION_FORBIDDEN",
    ):
        build_internal_model_gateway(
            settings=Settings(_env_file=None),
            route=_route(provider_code="EXTERNAL", digest="a" * 64),
        )


def test_internal_model_fails_closed_until_executor_is_approved() -> None:
    with pytest.raises(
        InternalModelRuntimeConfigurationError,
        match="INTERNAL_MODEL_EXECUTOR_NOT_IMPLEMENTED",
    ):
        build_internal_model_gateway(
            settings=Settings(_env_file=None),
            route=_route(provider_code="INTERNAL_MODEL", digest="b" * 64),
        )
