from __future__ import annotations

import re

from hamoon.app.config.settings import Settings
from hamoon.domains.intelligence.domain.registry import (
    INTERNAL_MODEL_PROVIDER_CODE,
    ResolvedAIRoute,
)
from hamoon.infrastructure.ai.gateway import ProviderAIGateway


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

    # The internal executor/training implementation is intentionally absent
    # until its model family, training algorithm and execution contract are
    # explicitly approved. Production therefore fails closed and routes work
    # to a human instead of silently selecting an implementation.
    raise InternalModelRuntimeConfigurationError(
        "INTERNAL_MODEL_EXECUTOR_NOT_IMPLEMENTED"
    )
