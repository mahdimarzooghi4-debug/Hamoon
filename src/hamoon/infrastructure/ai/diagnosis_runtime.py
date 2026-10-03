from uuid import UUID

from pydantic import JsonValue

from hamoon.domains.intelligence.domain.decisions import AIExecutionResult
from hamoon.domains.intelligence.domain.entities import FeaturePackage
from hamoon.domains.intelligence.ports.ai import DiagnosisAIClient
from hamoon.infrastructure.ai.contracts import (
    AIRoutingPolicy,
    AITaskClass,
    StructuredAIRequest,
)
from hamoon.infrastructure.ai.gateway import ProviderAIGateway


DIAGNOSIS_V1_SCHEMA: dict[str, JsonValue] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "summary", "items", "review_flags"],
    "properties": {
        "schema_version": {"const": "diagnosis-v1"},
        "summary": {"type": "string", "minLength": 1, "maxLength": 2000},
        "items": {
            "type": "array",
            "maxItems": 50,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "code",
                    "category",
                    "title",
                    "rationale",
                    "supporting_feature_refs",
                    "uncertainty",
                ],
                "properties": {
                    "code": {"type": "string", "minLength": 1, "maxLength": 150},
                    "category": {
                        "enum": ["NEED", "RISK", "CAPACITY", "CONSTRAINT"]
                    },
                    "title": {"type": "string", "minLength": 1, "maxLength": 300},
                    "rationale": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 2000,
                    },
                    "supporting_feature_refs": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1, "maxLength": 300},
                        "uniqueItems": True,
                    },
                    "uncertainty": {
                        "enum": ["LOW", "MEDIUM", "HIGH", "UNKNOWN"]
                    },
                },
            },
        },
        "review_flags": {
            "type": "array",
            "items": {"type": "string", "minLength": 1, "maxLength": 150},
            "uniqueItems": True,
        },
    },
}


class GatewayDiagnosisAIClient(DiagnosisAIClient):
    def __init__(
        self,
        *,
        gateway: ProviderAIGateway,
        routing_policy: AIRoutingPolicy,
    ) -> None:
        self._gateway = gateway
        self._routing_policy = routing_policy

    async def generate_diagnosis(
        self,
        *,
        feature_package: FeaturePackage,
        correlation_id: str,
    ) -> AIExecutionResult:
        result = await self._gateway.generate_structured(
            request=StructuredAIRequest(
                task_class=AITaskClass.DIAGNOSIS,
                feature_package_id=feature_package.id,
                feature_schema_version=feature_package.schema_version,
                features=feature_package.provider_payload(),
                correlation_id=correlation_id,
            ),
            routing_policy=self._routing_policy,
            output_schema=DIAGNOSIS_V1_SCHEMA,
        )
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


def local_fake_diagnosis_policy() -> AIRoutingPolicy:
    return AIRoutingPolicy(
        id=UUID("00000000-0000-0000-0000-000000000601"),
        version="local-test-v1",
        task_class=AITaskClass.DIAGNOSIS,
        provider_code="FAKE",
        model_alias="hamoon.diagnosis.v1",
        concrete_model_id="fake-diagnosis-v1",
        prompt_policy_version="diagnosis-prompt-v1",
        output_schema_version="diagnosis-v1",
        structured_output_required=True,
    )
