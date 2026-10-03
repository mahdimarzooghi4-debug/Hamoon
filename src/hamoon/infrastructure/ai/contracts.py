from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from pydantic import JsonValue


class AITaskClass(StrEnum):
    DIAGNOSIS = "DIAGNOSIS"
    PRESCRIPTION = "PRESCRIPTION"
    PROVIDER_MATCH_EXPLANATION = "PROVIDER_MATCH_EXPLANATION"
    CASE_SUMMARY = "CASE_SUMMARY"
    EVIDENCE_SYNTHESIS = "EVIDENCE_SYNTHESIS"
    DATA_ANOMALY_EXPLANATION = "DATA_ANOMALY_EXPLANATION"
    OUTCOME_INTERPRETATION = "OUTCOME_INTERPRETATION"
    COPILOT_ASSIST = "COPILOT_ASSIST"


@dataclass(frozen=True, slots=True)
class AIRoutingPolicy:
    id: UUID
    version: str
    task_class: AITaskClass
    provider_code: str
    model_alias: str
    concrete_model_id: str
    prompt_policy_version: str
    output_schema_version: str
    structured_output_required: bool = True


@dataclass(frozen=True, slots=True)
class StructuredAIRequest:
    task_class: AITaskClass
    feature_package_id: UUID
    feature_schema_version: str
    features: dict[str, JsonValue]
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ProviderStructuredRequest:
    task_class: AITaskClass
    model_id: str
    model_alias: str
    prompt_policy_version: str
    output_schema_version: str
    feature_schema_version: str
    instructions: str
    output_schema: dict[str, JsonValue]
    features: dict[str, JsonValue]
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ProviderStructuredResponse:
    provider_code: str
    model_id: str
    output: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class StructuredAIResult:
    feature_package_id: UUID
    feature_schema_version: str
    provider_code: str
    model_id: str
    model_alias: str
    routing_policy_id: UUID
    routing_policy_version: str
    prompt_policy_version: str
    output_schema_version: str
    output: dict[str, JsonValue]
