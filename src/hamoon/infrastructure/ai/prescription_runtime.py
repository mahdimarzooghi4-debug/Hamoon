from typing import cast
from uuid import UUID

from pydantic import JsonValue

from hamoon.domains.intelligence.domain.decisions import AIExecutionResult
from hamoon.domains.intelligence.domain.entities import FeaturePackage
from hamoon.domains.prescription.domain.errors import PrescriptionGenerationError
from hamoon.domains.prescription.ports.ai import PrescriptionAIClient
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

INTERVENTION_TYPES = [
    "COUNSELING",
    "MOTIVATION",
    "PSYCHOLOGICAL_EMPOWERMENT",
    "COACHING",
    "TRAINING",
    "SKILLS_TRAINING",
    "VOCATIONAL_TRAINING",
    "MARKET_LINKAGE",
    "EMPLOYMENT",
    "FINANCING_FACILITIES",
    "NETWORKING",
    "SOCIAL_SUPPORT",
    "TREATMENT",
    "RISK_REDUCTION",
    "STABILIZATION",
]

PRESCRIPTION_V1_SCHEMA: dict[str, JsonValue] = cast(dict[str, JsonValue], {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "summary",
        "intensity_score",
        "items",
        "review_flags",
    ],
    "properties": {
        "schema_version": {"const": "prescription-v1"},
        "summary": {"type": "string", "minLength": 1, "maxLength": 2000},
        "intensity_score": {
            "type": "string",
            "pattern": r"^(0(?:\.\d+)?|1(?:\.0+)?)$",
        },
        "items": {
            "type": "array",
            "minItems": 1,
            "maxItems": 20,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "code",
                    "target_variable",
                    "intervention_type",
                    "priority_rank",
                    "title",
                    "rationale",
                    "success_criteria",
                    "review_schedule",
                    "diagnosis_refs",
                    "supporting_feature_refs",
                ],
                "properties": {
                    "code": {"type": "string", "minLength": 1, "maxLength": 150},
                    "target_variable": {"enum": ["P", "G", "O", "R"]},
                    "intervention_type": {"enum": INTERVENTION_TYPES},
                    "priority_rank": {"type": "integer", "minimum": 1, "maximum": 20},
                    "title": {"type": "string", "minLength": 1, "maxLength": 300},
                    "rationale": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 2000,
                    },
                    "success_criteria": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 10,
                        "items": {"type": "string", "minLength": 1, "maxLength": 500},
                    },
                    "review_schedule": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["review_after_days", "rationale"],
                        "properties": {
                            "review_after_days": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 730,
                            },
                            "rationale": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 1000,
                            },
                        },
                    },
                    "diagnosis_refs": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string", "minLength": 1, "maxLength": 200},
                        "uniqueItems": True,
                    },
                    "supporting_feature_refs": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string", "minLength": 1, "maxLength": 300},
                        "uniqueItems": True,
                    },
                },
            },
        },
        "review_flags": {
            "type": "array",
            "contains": {"const": "HUMAN_REVIEW_REQUIRED"},
            "items": {"type": "string", "minLength": 1, "maxLength": 150},
            "uniqueItems": True,
        },
    },
})


class GatewayPrescriptionAIClient(PrescriptionAIClient):
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

    async def generate_prescription(
        self,
        *,
        feature_package: FeaturePackage,
        correlation_id: str,
    ) -> AIExecutionResult:
        try:
            result = await self._gateway.generate_structured(
                request=StructuredAIRequest(
                    task_class=AITaskClass.PRESCRIPTION,
                    feature_package_id=feature_package.id,
                    feature_schema_version=feature_package.schema_version,
                    features=feature_package.provider_payload(),
                    correlation_id=correlation_id,
                ),
                routing_policy=self._routing_policy,
                output_schema=PRESCRIPTION_V1_SCHEMA,
                instructions=self._instructions,
            )
        except AIOutputSchemaError as exc:
            raise PrescriptionGenerationError("AI_OUTPUT_SCHEMA_INVALID") from exc
        except AIRoutingError as exc:
            raise PrescriptionGenerationError("AI_ROUTING_FAILED") from exc
        except AIProviderExecutionError as exc:
            raise PrescriptionGenerationError("AI_PROVIDER_UNAVAILABLE") from exc

        return AIExecutionResult(
            provider_code=result.provider_code,
            model_id=result.model_id,
            model_alias=result.model_alias,
            routing_policy_id=result.routing_policy_id,
            routing_policy_version=result.routing_policy_version,
            prompt_policy_version=result.prompt_policy_version,
            output_schema_version=result.output_schema_version,
            output=result.output,
        )


def local_fake_prescription_policy() -> AIRoutingPolicy:
    return AIRoutingPolicy(
        id=UUID("00000000-0000-0000-0000-000000000621"),
        version="local-prescription-test-v1",
        task_class=AITaskClass.PRESCRIPTION,
        provider_code="FAKE",
        model_alias="hamoon.prescription.v1",
        concrete_model_id="fake-prescription-v1",
        prompt_policy_version="prescription-prompt-v1",
        output_schema_version="prescription-v1",
        structured_output_required=True,
    )
