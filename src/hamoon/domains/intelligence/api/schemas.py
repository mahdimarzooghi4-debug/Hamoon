from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, JsonValue

from hamoon.infrastructure.ai.contracts import AITaskClass

from hamoon.domains.intelligence.domain.decisions import (
    AIDecisionStatus,
    AIDecisionType,
    DiagnosisStatus,
    HumanDecisionAction,
)

class GenerateDiagnosisRequest(BaseModel):
    pgor_snapshot_id: UUID

class GenerateDiagnosisData(BaseModel):
    diagnosis_id: UUID
    ai_decision_id: UUID
    status: DiagnosisStatus
    version: int
    trace_id: UUID

class GenerateDiagnosisResponse(BaseModel):
    data: GenerateDiagnosisData

class DiagnosisData(BaseModel):
    id: UUID
    household_id: UUID
    ai_decision_id: UUID
    status: DiagnosisStatus
    version: int
    machine_proposal: dict[str, JsonValue]
    accepted_payload: dict[str, JsonValue] | None
    created_at: datetime
    reviewed_at: datetime | None
    reviewed_by: UUID | None

class DiagnosisResponse(BaseModel):
    data: DiagnosisData

class ConfirmDiagnosisRequest(BaseModel):
    expected_version: int = Field(ge=1)
    reason_code: str | None = Field(default=None, max_length=100)
    reason_text: str | None = Field(default=None, max_length=1000)

class StructuredDiagnosisReviewRequest(ConfirmDiagnosisRequest):
    modified_payload: dict[str, JsonValue]

class ReviewDiagnosisData(BaseModel):
    diagnosis_id: UUID
    ai_decision_id: UUID
    human_decision_id: UUID
    learning_signal_id: UUID
    action: HumanDecisionAction
    status: DiagnosisStatus
    version: int
    accepted_payload: dict[str, JsonValue] | None

class ReviewDiagnosisResponse(BaseModel):
    data: ReviewDiagnosisData

class AIDecisionData(BaseModel):
    id: UUID
    household_id: UUID
    assessment_id: UUID
    feature_package_id: UUID
    pgor_snapshot_id: UUID
    decision_type: AIDecisionType
    status: AIDecisionStatus
    provider_code: str
    model_id: str
    model_alias: str
    routing_policy_id: UUID
    routing_policy_version: str
    prompt_policy_version: str
    output_schema_version: str
    structured_output: dict[str, JsonValue]
    trace_id: UUID
    generated_at: datetime

class AIDecisionResponse(BaseModel):
    data: AIDecisionData

class DecisionTraceData(BaseModel):
    id: UUID
    household_id: UUID
    trace_type: AIDecisionType
    state_fingerprint: str
    pgor_snapshot_id: UUID
    feature_package_id: UUID
    ai_decision_id: UUID
    human_decision_id: UUID | None
    opened_at: datetime
    closed_at: datetime | None

class DecisionTraceResponse(BaseModel):
    data: DecisionTraceData

class CompleteAIEvaluationRequest(BaseModel):
    dataset_manifest_digest: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )
    report: dict[str, JsonValue]

class AIEvaluationRunData(BaseModel):
    id: UUID
    task_class: str
    model_version_id: UUID
    prompt_policy_version_id: UUID
    evaluation_policy_version: str
    dataset_version_id: UUID | None
    dataset_manifest_digest: str | None
    report_digest: str | None
    status: str
    passed: bool
    summary_metrics: dict[str, JsonValue]
    started_at: datetime | None
    completed_at: datetime | None

class AIEvaluationRunResponse(BaseModel):
    data: AIEvaluationRunData

class AIRoutingPromotionData(BaseModel):
    routing_policy_id: UUID
    model_version_id: UUID
    task_class: str
    routing_version: str
    model_status: str
    routing_status: str
    activated_at: datetime

class AIRoutingPromotionResponse(BaseModel):
    data: AIRoutingPromotionData



class CreateAIRoutingPolicyRequest(BaseModel):
    task_class: AITaskClass
    version: str = Field(min_length=1, max_length=100)
    model_alias: str = Field(min_length=1, max_length=150)
    model_version_id: UUID
    prompt_policy_version_id: UUID
    evaluation_run_id: UUID


class AIRoutingPolicyDraftData(BaseModel):
    routing_policy_id: UUID
    task_class: AITaskClass
    version: str
    model_alias: str
    model_version_id: UUID
    prompt_policy_version_id: UUID
    evaluation_run_id: UUID
    status: str


class AIRoutingPolicyDraftResponse(BaseModel):
    data: AIRoutingPolicyDraftData


class DiagnosisHumanDecisionData(BaseModel):
    id: UUID
    actor_id: UUID
    action: HumanDecisionAction
    reason_code: str | None
    reason_text: str | None
    accepted_payload: dict[str, JsonValue] | None
    modified_payload: dict[str, JsonValue] | None
    decided_at: datetime


class DiagnosisHistoryEntryData(BaseModel):
    id: UUID
    household_id: UUID
    ai_decision_id: UUID
    status: DiagnosisStatus
    version: int
    machine_proposal: dict[str, JsonValue]
    accepted_payload: dict[str, JsonValue] | None
    model_alias: str
    output_schema_version: str
    generated_at: datetime
    created_at: datetime
    reviewed_at: datetime | None
    reviewed_by: UUID | None
    human_decisions: list[DiagnosisHumanDecisionData]


class DiagnosisHistoryResponse(BaseModel):
    data: list[DiagnosisHistoryEntryData]


class AIModelVersionCatalogData(BaseModel):
    id: UUID
    ai_model_id: UUID
    model_key: str
    purpose: str
    provider_id: UUID
    provider_code: str
    provider_status: str
    version: str
    concrete_model_id: str
    status: str
    limitations: str | None
    approved_at: datetime | None
    deployed_at: datetime | None


class AIModelVersionCatalogResponse(BaseModel):
    data: list[AIModelVersionCatalogData]


class PromptPolicyVersionCatalogData(BaseModel):
    id: UUID
    prompt_policy_id: UUID
    policy_name: str
    purpose: str
    version: str
    output_schema_version: str
    guardrail_version: str
    status: str
    approved_at: datetime | None


class PromptPolicyVersionCatalogResponse(BaseModel):
    data: list[PromptPolicyVersionCatalogData]


class AIEvaluationRunListResponse(BaseModel):
    data: list[AIEvaluationRunData]


class AIRoutingPolicyCatalogData(BaseModel):
    id: UUID
    task_class: str
    version: str
    model_alias: str
    model_version_id: UUID
    prompt_policy_version_id: UUID
    evaluation_run_id: UUID
    structured_output_required: bool
    status: str
    approved_at: datetime | None


class AIRoutingPolicyCatalogResponse(BaseModel):
    data: list[AIRoutingPolicyCatalogData]
