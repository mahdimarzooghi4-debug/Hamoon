from __future__ import annotations

from hamoon.app.config.settings import Settings
from hamoon.domains.intelligence.domain.registry import (
    HAMOON_NATIVE_PROVIDER_CODE,
    ResolvedAIRoute,
)
from hamoon.infrastructure.ai.gateway import ProviderAIGateway
from hamoon.infrastructure.ai.providers.native import HamoonNativeAIProvider


class NativeAIRuntimeConfigurationError(RuntimeError):
    """Production AI route is not safely bound to Hamoon's native runtime."""


def build_native_gateway(
    *,
    settings: Settings,
    route: ResolvedAIRoute,
) -> ProviderAIGateway:
    if route.routing_policy.provider_code != HAMOON_NATIVE_PROVIDER_CODE:
        raise NativeAIRuntimeConfigurationError(
            "EXTERNAL_AI_PROVIDER_PRODUCTION_FORBIDDEN"
        )
    if route.routing_policy.model_artifact_sha256 is None:
        raise NativeAIRuntimeConfigurationError(
            "NATIVE_MODEL_ARTIFACT_DIGEST_REQUIRED"
        )
    try:
        provider = HamoonNativeAIProvider(model_root=settings.ai_model_root)
    except ValueError as exc:
        raise NativeAIRuntimeConfigurationError(str(exc)) from exc
    return ProviderAIGateway(
        providers={HAMOON_NATIVE_PROVIDER_CODE: provider}
    )
