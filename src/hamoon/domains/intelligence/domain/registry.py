from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import JsonValue

from hamoon.infrastructure.ai.contracts import AIRoutingPolicy, AITaskClass

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
    status: EvaluationStatus
    passed: bool
    summary_metrics: dict[str, JsonValue]
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
