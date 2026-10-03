from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.app.config.settings import Settings
from hamoon.domains.intelligence.infrastructure.repositories import (
    SqlAlchemyAIRuntimeRegistryRepository,
)
from hamoon.infrastructure.ai.contracts import AITaskClass
from hamoon.infrastructure.ai.gateway import ProviderAIGateway
from hamoon.infrastructure.ai.outcome_runtime import (
    GatewayOutcomeAIClient,
    local_fake_outcome_policy,
)
from hamoon.infrastructure.ai.providers.fake import FakeAIProvider
from hamoon.infrastructure.ai.providers.openai import OpenAIProvider


class OutcomeAIRuntimeConfigurationError(RuntimeError):
    """Outcome AI runtime has no safe active route."""


async def build_outcome_ai_client(
    *,
    session: AsyncSession,
    settings: Settings,
) -> GatewayOutcomeAIClient:
    if settings.environment.lower() in {"local", "test", "development"}:
        return GatewayOutcomeAIClient(
            gateway=ProviderAIGateway(providers={"FAKE": FakeAIProvider()}),
            routing_policy=local_fake_outcome_policy(),
        )

    route = await SqlAlchemyAIRuntimeRegistryRepository(session).resolve_active_route(
        AITaskClass.OUTCOME_INTERPRETATION
    )
    if route is None:
        raise OutcomeAIRuntimeConfigurationError("AI_ROUTING_POLICY_NOT_FOUND")
    if route.routing_policy.provider_code != "OPENAI":
        raise OutcomeAIRuntimeConfigurationError("AI_PROVIDER_UNSUPPORTED")
    if not settings.openai_api_key:
        raise OutcomeAIRuntimeConfigurationError("AI_PROVIDER_UNAVAILABLE")

    provider = OpenAIProvider(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout_seconds=settings.openai_timeout_seconds,
    )
    return GatewayOutcomeAIClient(
        gateway=ProviderAIGateway(providers={"OPENAI": provider}),
        routing_policy=route.routing_policy,
        instructions=route.instructions,
    )
