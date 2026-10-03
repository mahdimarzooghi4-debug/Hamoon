from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

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
