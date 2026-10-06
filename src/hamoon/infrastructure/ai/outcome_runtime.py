from typing import cast
from uuid import UUID

from pydantic import JsonValue

from hamoon.domains.intelligence.domain.decisions import AIExecutionResult
from hamoon.domains.intelligence.domain.entities import FeaturePackage
from hamoon.domains.outcome.domain.errors import OutcomeInterpretationError
from hamoon.domains.outcome.ports.ai import OutcomeAIClient
from hamoon.infrastructure.ai.contracts import (
    AIRoutingPolicy,
    AITaskClass,
    StructuredAIRequest,
)
from hamoon.infrastructure.ai.gateway import (
    AIOutputSchemaError,
    AIProviderExecutionError,
    AIRoutingError,
    ProviderAIGateway,
)

OUTCOME_INTERPRETATION_V1_SCHEMA: dict[str, JsonValue] = cast(
    dict[str, JsonValue],
    {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "classification",
            "observed_change_summary",
            "causal_claim",
            "supporting_feature_refs",
            "review_flags",
        ],
        "properties": {
            "schema_version": {"const": "outcome-interpretation-v1"},
            "classification": {
                "type": "string",
                "enum": [
                    "GOAL_ACHIEVED",
                    "PROGRESS",
                    "NO_SIGNIFICANT_CHANGE",
                    "REGRESSION",
                    "NEEDS_MORE_TIME",
                    "NEEDS_MORE_DATA",
                ],
            },
            "observed_change_summary": {
                "type": "string",
                "minLength": 1,
                "maxLength": 4000,
            },
            "causal_claim": {"const": False},
            "supporting_feature_refs": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1, "maxLength": 300},
                "uniqueItems": True,
            },
            "review_flags": {
                "type": "array",
                "contains": {"const": "HUMAN_REVIEW_REQUIRED"},
                "items": {"type": "string", "minLength": 1, "maxLength": 150},
                "uniqueItems": True,
            },
        },
    },
)


class GatewayOutcomeAIClient(OutcomeAIClient):
    def __init__(
        self,
        *,
        gateway: ProviderAIGateway,
        routing_policy: AIRoutingPolicy,
        instructions: str = "",
    ) -> None:
        self._gateway = gateway
        self._routing_policy = routing_policy
        self._instructions = instructions

    async def generate_outcome_interpretation(
        self,
        *,
        feature_package: FeaturePackage,
        correlation_id: str,
    ) -> AIExecutionResult:
        try:
            result = await self._gateway.generate_structured(
                request=StructuredAIRequest(
                    task_class=AITaskClass.OUTCOME_INTERPRETATION,
                    feature_package_id=feature_package.id,
                    feature_schema_version=feature_package.schema_version,
                    features=feature_package.provider_payload(),
                    correlation_id=correlation_id,
                ),
                routing_policy=self._routing_policy,
                output_schema=OUTCOME_INTERPRETATION_V1_SCHEMA,
                instructions=self._instructions,
            )
        except AIOutputSchemaError as exc:
            raise OutcomeInterpretationError("AI_OUTPUT_SCHEMA_INVALID") from exc
        except AIRoutingError as exc:
            raise OutcomeInterpretationError("AI_ROUTING_FAILED") from exc
        except AIProviderExecutionError as exc:
            raise OutcomeInterpretationError("AI_PROVIDER_UNAVAILABLE") from exc

        return AIExecutionResult(
            provider_code=result.provider_code,
            model_id=result.model_id,
            model_alias=result.model_alias,
            routing_policy_id=result.routing_policy_id,
            routing_policy_version=result.routing_policy_version,
            prompt_policy_version=result.prompt_policy_version,
            output_schema_version=result.output_schema_version,
            output=result.output,
            model_artifact_sha256=result.model_artifact_sha256,
        )


def local_fake_outcome_policy() -> AIRoutingPolicy:
    return AIRoutingPolicy(
        id=UUID("00000000-0000-0000-0000-000000000631"),
        version="local-outcome-test-v1",
        task_class=AITaskClass.OUTCOME_INTERPRETATION,
        provider_code="FAKE",
        model_alias="hamoon.outcome.v1",
        concrete_model_id="fake-outcome-v1",
        prompt_policy_version="outcome-prompt-v1",
        output_schema_version="outcome-interpretation-v1",
        structured_output_required=True,
    )
