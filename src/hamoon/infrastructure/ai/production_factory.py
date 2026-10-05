from __future__ import annotations

from pathlib import Path

from hamoon.app.config.settings import Settings
from hamoon.domains.intelligence.domain.registry import ResolvedAIRoute
from hamoon.infrastructure.ai.gateway import ProviderAIGateway
from hamoon.infrastructure.ai.providers.local_artifact import LocalArtifactAIProvider

LOCAL_AI_PROVIDER_CODE = "HAMOON_LOCAL"


class LocalAIRuntimeConfigurationError(RuntimeError):
    """Production AI is not safely bound to a local Hamoon model artifact."""


def build_local_ai_gateway(
    *,
    settings: Settings,
    route: ResolvedAIRoute,
) -> ProviderAIGateway:
    policy = route.routing_policy
    if policy.provider_code != LOCAL_AI_PROVIDER_CODE:
        raise LocalAIRuntimeConfigurationError(
            "EXTERNAL_OR_REMOTE_AI_PROVIDER_PRODUCTION_FORBIDDEN"
        )
    if policy.model_artifact_ref is None or policy.model_artifact_sha256 is None:
        raise LocalAIRuntimeConfigurationError(
            "LOCAL_MODEL_ARTIFACT_IDENTITY_REQUIRED"
        )

    try:
        provider = LocalArtifactAIProvider(
            model_root=Path(settings.ai_model_root),
            runner_path=Path(settings.ai_local_runner_path),
            timeout_seconds=settings.ai_local_runner_timeout_seconds,
        )
    except ValueError as exc:
        raise LocalAIRuntimeConfigurationError(str(exc)) from exc

    return ProviderAIGateway(providers={LOCAL_AI_PROVIDER_CODE: provider})
