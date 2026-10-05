from collections.abc import Mapping

from jsonschema import ValidationError, validate
from opentelemetry import trace
from pydantic import JsonValue

from hamoon.app.observability.metrics import AI_EXECUTIONS
from hamoon.app.observability.operational_events import (
    OperationalRuntimeEventType,
    record_operational_runtime_event_safe,
)
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


_tracer = trace.get_tracer("hamoon.ai.gateway")


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
        span = _tracer.start_span(
            "hamoon.ai.generate_structured",
            attributes={
                "hamoon.correlation_id": request.correlation_id,
                "hamoon.ai.task_class": request.task_class.value,
                "hamoon.ai.provider": routing_policy.provider_code,
                "hamoon.ai.model_alias": routing_policy.model_alias,
                "hamoon.ai.routing_policy_version": routing_policy.version,
                "hamoon.ai.prompt_policy_version": routing_policy.prompt_policy_version,
                "hamoon.ai.output_schema_version": routing_policy.output_schema_version,
                "hamoon.ai.feature_schema_version": request.feature_schema_version,
            },
        )
        if routing_policy.task_class is not request.task_class:
            span.set_attribute("hamoon.ai.status", "routing_error")
            span.end()
            AI_EXECUTIONS.labels(**labels, status="routing_error").inc()
            await record_operational_runtime_event_safe(
                event_type=OperationalRuntimeEventType.AI_ROUTING_FAILURE,
                source="ai.gateway",
                detail_code="TASK_CLASS_MISMATCH",
                correlation_id=request.correlation_id,
                dimensions={
                    "task_class": request.task_class.value,
                    "provider": routing_policy.provider_code,
                },
            )
            raise AIRoutingError("Routing policy task does not match request task.")
        if not routing_policy.structured_output_required:
            span.set_attribute("hamoon.ai.status", "routing_error")
            span.end()
            AI_EXECUTIONS.labels(**labels, status="routing_error").inc()
            await record_operational_runtime_event_safe(
                event_type=OperationalRuntimeEventType.AI_ROUTING_FAILURE,
                source="ai.gateway",
                detail_code="STRUCTURED_OUTPUT_REQUIRED",
                correlation_id=request.correlation_id,
                dimensions={
                    "task_class": request.task_class.value,
                    "provider": routing_policy.provider_code,
                },
            )
            raise AIRoutingError("Decision-producing task requires structured output.")

        provider = self._providers.get(routing_policy.provider_code)
        if provider is None:
            span.set_attribute("hamoon.ai.status", "routing_error")
            span.end()
            AI_EXECUTIONS.labels(**labels, status="routing_error").inc()
            await record_operational_runtime_event_safe(
                event_type=OperationalRuntimeEventType.AI_ROUTING_FAILURE,
                source="ai.gateway",
                detail_code="PROVIDER_ADAPTER_UNAVAILABLE",
                correlation_id=request.correlation_id,
                dimensions={
                    "task_class": request.task_class.value,
                    "provider": routing_policy.provider_code,
                },
            )
            raise AIRoutingError("Configured provider adapter is unavailable.")

        try:
            response = await provider.generate_structured(
                ProviderStructuredRequest(
                task_class=request.task_class,
                model_id=routing_policy.concrete_model_id,
                model_alias=routing_policy.model_alias,
                model_artifact_ref=routing_policy.model_artifact_ref,
                model_artifact_sha256=routing_policy.model_artifact_sha256,
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
            span.record_exception(exc)
            span.set_attribute("hamoon.ai.status", "provider_error")
            span.end()
            AI_EXECUTIONS.labels(**labels, status="provider_error").inc()
            await record_operational_runtime_event_safe(
                event_type=OperationalRuntimeEventType.AI_INFERENCE_FAILURE,
                source="ai.gateway",
                detail_code="AI_PROVIDER_EXECUTION_FAILED",
                correlation_id=request.correlation_id,
                dimensions={
                    "task_class": request.task_class.value,
                    "provider": routing_policy.provider_code,
                },
            )
            raise AIProviderExecutionError("AI_PROVIDER_EXECUTION_FAILED") from exc

        try:
            validate(instance=response.output, schema=output_schema)
        except ValidationError as exc:
            span.record_exception(exc)
            span.set_attribute("hamoon.ai.status", "schema_error")
            span.end()
            AI_EXECUTIONS.labels(**labels, status="schema_error").inc()
            await record_operational_runtime_event_safe(
                event_type=OperationalRuntimeEventType.AI_SCHEMA_FAILURE,
                source="ai.gateway",
                detail_code="AI_OUTPUT_SCHEMA_INVALID",
                correlation_id=request.correlation_id,
                dimensions={
                    "task_class": request.task_class.value,
                    "provider": routing_policy.provider_code,
                },
            )
            raise AIOutputSchemaError("AI_OUTPUT_SCHEMA_INVALID") from exc

        AI_EXECUTIONS.labels(**labels, status="success").inc()
        span.set_attribute("hamoon.ai.status", "success")
        span.end()
        return StructuredAIResult(
            feature_package_id=request.feature_package_id,
            feature_schema_version=request.feature_schema_version,
            provider_code=response.provider_code,
            model_id=response.model_id,
            model_alias=routing_policy.model_alias,
            model_artifact_sha256=response.model_artifact_sha256,
            routing_policy_id=routing_policy.id,
            routing_policy_version=routing_policy.version,
            prompt_policy_version=routing_policy.prompt_policy_version,
            output_schema_version=routing_policy.output_schema_version,
            output=response.output,
        )
