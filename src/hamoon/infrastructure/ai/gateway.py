from collections.abc import Mapping

from jsonschema import ValidationError, validate
from pydantic import JsonValue

from hamoon.app.observability.metrics import AI_EXECUTIONS
from hamoon.infrastructure.ai.contracts import (
    AIRoutingPolicy,
    ProviderStructuredRequest,
    StructuredAIRequest,
    StructuredAIResult,
)
from hamoon.infrastructure.ai.providers.base import AIProviderAdapter


class AIOutputSchemaError(ValueError):
    """Provider output failed the approved structured-output schema."""


class AIRoutingError(ValueError):
    """Routing policy cannot be satisfied by configured providers."""


class AIProviderExecutionError(RuntimeError):
    """Configured provider failed before a valid structured result was returned."""


class ProviderAIGateway:
    def __init__(
        self,
        *,
        providers: Mapping[str, AIProviderAdapter],
    ) -> None:
        self._providers = providers

    async def generate_structured(
        self,
        *,
        request: StructuredAIRequest,
        routing_policy: AIRoutingPolicy,
        output_schema: dict[str, JsonValue],
        instructions: str = "",
    ) -> StructuredAIResult:
        labels = {
            "task_class": request.task_class.value,
            "provider": routing_policy.provider_code,
        }
        if routing_policy.task_class is not request.task_class:
            AI_EXECUTIONS.labels(**labels, status="routing_error").inc()
            raise AIRoutingError("Routing policy task does not match request task.")
        if not routing_policy.structured_output_required:
            AI_EXECUTIONS.labels(**labels, status="routing_error").inc()
            raise AIRoutingError("Decision-producing task requires structured output.")

        provider = self._providers.get(routing_policy.provider_code)
        if provider is None:
            AI_EXECUTIONS.labels(**labels, status="routing_error").inc()
            raise AIRoutingError("Configured provider adapter is unavailable.")

        try:
            response = await provider.generate_structured(
                ProviderStructuredRequest(
                task_class=request.task_class,
                model_id=routing_policy.concrete_model_id,
                model_alias=routing_policy.model_alias,
                prompt_policy_version=routing_policy.prompt_policy_version,
                output_schema_version=routing_policy.output_schema_version,
                feature_schema_version=request.feature_schema_version,
                instructions=instructions,
                output_schema=output_schema,
                features=request.features,
                correlation_id=request.correlation_id,
                )
            )
        except Exception as exc:
            AI_EXECUTIONS.labels(**labels, status="provider_error").inc()
            raise AIProviderExecutionError("AI_PROVIDER_EXECUTION_FAILED") from exc

        try:
            validate(instance=response.output, schema=output_schema)
        except ValidationError as exc:
            AI_EXECUTIONS.labels(**labels, status="schema_error").inc()
            raise AIOutputSchemaError("AI_OUTPUT_SCHEMA_INVALID") from exc

        AI_EXECUTIONS.labels(**labels, status="success").inc()
        return StructuredAIResult(
            feature_package_id=request.feature_package_id,
            feature_schema_version=request.feature_schema_version,
            provider_code=response.provider_code,
            model_id=response.model_id,
            model_alias=routing_policy.model_alias,
            routing_policy_id=routing_policy.id,
            routing_policy_version=routing_policy.version,
            prompt_policy_version=routing_policy.prompt_policy_version,
            output_schema_version=routing_policy.output_schema_version,
            output=response.output,
        )
