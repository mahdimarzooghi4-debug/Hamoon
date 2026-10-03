from dataclasses import dataclass
from uuid import UUID

from hamoon.domains.intelligence.domain.decisions import LearningSignalQuality
from hamoon.infrastructure.ai.contracts import AITaskClass


@dataclass(frozen=True, slots=True)
class CurateLearningSignalCommand:
    signal_id: UUID
    expected_quality_status: LearningSignalQuality
    to_quality_status: LearningSignalQuality
    reason_code: str
    actor_id: UUID
    request_id: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class CreateOutcomeDatasetCommand:
    dataset_key: str
    version: str
    selection_policy_version: str
    signal_ids: tuple[UUID, ...]
    actor_id: UUID
    request_id: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ApproveDatasetCommand:
    dataset_id: UUID
    actor_id: UUID
    request_id: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class CreateEvaluationRunCommand:
    task_class: AITaskClass
    model_version_id: UUID
    prompt_policy_version_id: UUID
    dataset_version_id: UUID
    evaluation_policy_version: str
    actor_id: UUID
    request_id: str
    correlation_id: str
