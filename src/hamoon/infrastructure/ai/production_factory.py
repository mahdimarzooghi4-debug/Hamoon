from __future__ import annotations

import re

from hamoon.app.config.settings import Settings
from hamoon.domains.intelligence.domain.registry import (
    INTERNAL_MODEL_PROVIDER_CODE,
    ResolvedAIRoute,
)
from hamoon.infrastructure.ai.contracts import InternalModelExecutionMode
from hamoon.infrastructure.ai.gateway import ProviderAIGateway
from hamoon.infrastructure.ai.internal_model import get_internal_model_runtime


INTERNAL_MODEL_EXECUTION_MODE = InternalModelExecutionMode.IN_PROCESS


class InternalModelRuntimeConfigurationError(RuntimeError):
    """Production INTERNAL_MODEL runtime is not safely executable."""


def build_internal_model_gateway(
    *,
    settings: Settings,
    route: ResolvedAIRoute,
) -> ProviderAIGateway:
    del settings

    if route.routing_policy.provider_code != INTERNAL_MODEL_PROVIDER_CODE:
        raise InternalModelRuntimeConfigurationError(
            "EXTERNAL_AI_PROVIDER_PRODUCTION_FORBIDDEN"
        )

    digest = route.routing_policy.model_artifact_sha256
    if digest is None or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise InternalModelRuntimeConfigurationError(
            "INTERNAL_MODEL_ARTIFACT_DIGEST_REQUIRED"
        )

    runtime = get_internal_model_runtime()
    if runtime is None:
        raise InternalModelRuntimeConfigurationError(
            "INTERNAL_MODEL_RUNTIME_NOT_CONFIGURED"
        )
    if route.routing_policy.concrete_model_id not in runtime.executors:
        raise InternalModelRuntimeConfigurationError(
            "INTERNAL_MODEL_EXECUTOR_NOT_REGISTERED"
        )

    return ProviderAIGateway(
        providers={
            INTERNAL_MODEL_PROVIDER_CODE: runtime.provider_adapter(),
        }
    )
