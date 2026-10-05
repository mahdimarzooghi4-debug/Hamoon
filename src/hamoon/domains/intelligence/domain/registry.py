from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import JsonValue

from hamoon.infrastructure.ai.contracts import AIRoutingPolicy, AITaskClass

HAMOON_LOCAL_PROVIDER_CODE = "HAMOON_LOCAL"

class AIProviderStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"

class AIModelVersionStatus(StrEnum):
    EXPERIMENT = "EXPERIMENT"
    CANDIDATE = "CANDIDATE"
    APPROVED = "APPROVED"
    PRODUCTION = "PRODUCTION"
    RETIRED = "RETIRED"

class PromptPolicyVersionStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"

class RoutingPolicyStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"

class EvaluationStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"


class ModelTrainingStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"

@dataclass(frozen=True, slots=True)
class ModelTrainingRunState:
    id: UUID
    task_class: AITaskClass
    model_key: str
    target_version: str
    concrete_model_id: str
    artifact_ref: str
    training_dataset_version_id: UUID
    training_dataset_manifest_digest: str
    training_recipe_version: str
    parent_model_version_id: UUID | None
    parent_model_artifact_sha256: str | None
    limitations: str | None
    status: ModelTrainingStatus
    workflow_id: str
    candidate_model_version_id: UUID | None
    error_code: str | None
    requested_at: datetime
    requested_by: UUID
    started_at: datetime | None
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class ResolvedAIRoute:
    routing_policy: AIRoutingPolicy
    instructions: str
    evaluation_run_id: UUID
    evaluation_completed_at: datetime

    @property
    def task_class(self) -> AITaskClass:
        return self.routing_policy.task_class

@dataclass(frozen=True, slots=True)
class EvaluationRunState:
    id: UUID
    task_class: AITaskClass
    model_version_id: UUID
    prompt_policy_version_id: UUID
    evaluation_policy_version: str
    dataset_version_id: UUID | None
    dataset_manifest_digest: str | None
    report_digest: str | None
    status: EvaluationStatus
    passed: bool
    summary_metrics: dict[str, JsonValue]
    started_at: datetime | None
    completed_at: datetime | None

@dataclass(frozen=True, slots=True)
class RoutingPromotionResult:
    routing_policy_id: UUID
    model_version_id: UUID
    task_class: AITaskClass
    routing_version: str
    model_status: AIModelVersionStatus
    routing_status: RoutingPolicyStatus
    activated_at: datetime



@dataclass(frozen=True, slots=True)
class RoutingPolicyDraft:
    id: UUID
    task_class: AITaskClass
    version: str
    model_alias: str
    model_version_id: UUID
    prompt_policy_version_id: UUID
    evaluation_run_id: UUID
    status: RoutingPolicyStatus


@dataclass(frozen=True, slots=True)
class AIModelVersionCatalogItem:
    id: UUID
    ai_model_id: UUID
    model_key: str
    purpose: str
    provider_id: UUID
    provider_code: str
    provider_status: AIProviderStatus
    version: str
    concrete_model_id: str
    artifact_ref: str | None
    artifact_sha256: str | None
    parent_model_version_id: UUID | None
    training_dataset_version_id: UUID | None
    training_dataset_manifest_digest: str | None
    training_recipe_version: str | None
    trained_at: datetime | None
    status: AIModelVersionStatus
    limitations: str | None
    approved_at: datetime | None
    deployed_at: datetime | None


@dataclass(frozen=True, slots=True)
class PromptPolicyVersionCatalogItem:
    id: UUID
    prompt_policy_id: UUID
    policy_name: str
    purpose: str
    version: str
    output_schema_version: str
    guardrail_version: str
    status: PromptPolicyVersionStatus
    approved_at: datetime | None


@dataclass(frozen=True, slots=True)
class RoutingPolicyCatalogItem:
    id: UUID
    task_class: AITaskClass
    version: str
    model_alias: str
    model_version_id: UUID
    prompt_policy_version_id: UUID
    evaluation_run_id: UUID
    structured_output_required: bool
    status: RoutingPolicyStatus
    approved_at: datetime | None
