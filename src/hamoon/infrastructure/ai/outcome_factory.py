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
from hamoon.infrastructure.ai.production_factory import (
    LocalAIRuntimeConfigurationError,
    build_local_ai_gateway,
)


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
    try:
        gateway = build_local_ai_gateway(
            settings=settings,
            route=route,
        )
    except LocalAIRuntimeConfigurationError as exc:
        raise OutcomeAIRuntimeConfigurationError(str(exc)) from exc

    return GatewayOutcomeAIClient(
        gateway=gateway,
        routing_policy=route.routing_policy,
        instructions=route.instructions,
    )
