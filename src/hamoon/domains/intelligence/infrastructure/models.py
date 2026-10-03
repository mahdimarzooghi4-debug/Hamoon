from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, JSON, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import JsonValue

from hamoon.domains.intelligence.domain.decisions import (
    AIDecisionStatus,
    AIDecisionType,
    DiagnosisStatus,
    HumanDecisionAction,
    HumanDecisionContext,
    LearningSignalQuality,
    LearningSignalType,
)
from hamoon.domains.intelligence.domain.entities import (
    FeaturePackageType,
    SensitivityClass,
)
from hamoon.domains.intelligence.domain.registry import (
    AIModelVersionStatus,
    AIProviderStatus,
    EvaluationStatus,
    PromptPolicyVersionStatus,
    RoutingPolicyStatus,
)
from hamoon.infrastructure.ai.contracts import AITaskClass
from hamoon.infrastructure.db.base import Base

class FeaturePackageModel(Base):
    __tablename__ = "feature_package"
    __table_args__ = (
        UniqueConstraint(
            "pgor_snapshot_id",
            "package_type",
            "schema_version",
            name="uq_feature_package_snapshot_type_schema",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("assessment.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    pgor_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    package_type: Mapped[FeaturePackageType] = mapped_column(
        Enum(FeaturePackageType, name="feature_package_type"),
        nullable=False,
    )
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    data_quality_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )

class FeatureValueModel(Base):
    __tablename__ = "feature_value"
    __table_args__ = (
        UniqueConstraint(
            "feature_package_id",
            "feature_key",
            name="uq_feature_value_package_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    feature_package_id: Mapped[UUID] = mapped_column(
        ForeignKey("feature_package.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_key: Mapped[str] = mapped_column(String(250), nullable=False)
    value_json: Mapped[JsonValue] = mapped_column(JSON, nullable=False)
    source_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    sensitivity_class: Mapped[SensitivityClass] = mapped_column(
        Enum(SensitivityClass, name="feature_sensitivity_class"),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

class AIDecisionModel(Base):
    __tablename__ = "ai_decision"
    __table_args__ = (
        UniqueConstraint("trace_id", name="uq_ai_decision_trace_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("assessment.id", ondelete="RESTRICT"),
        nullable=False,
    )
    feature_package_id: Mapped[UUID] = mapped_column(
        ForeignKey("feature_package.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    pgor_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    decision_type: Mapped[AIDecisionType] = mapped_column(
        Enum(AIDecisionType, name="ai_decision_type"),
        nullable=False,
    )
    status: Mapped[AIDecisionStatus] = mapped_column(
        Enum(AIDecisionStatus, name="ai_decision_status"),
        nullable=False,
    )
    provider_code: Mapped[str] = mapped_column(String(100), nullable=False)
    model_id: Mapped[str] = mapped_column(String(250), nullable=False)
    model_alias: Mapped[str] = mapped_column(String(150), nullable=False)
    routing_policy_id: Mapped[UUID] = mapped_column(nullable=False)
    routing_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    structured_output: Mapped[dict[str, JsonValue]] = mapped_column(JSON, nullable=False)
    trace_id: Mapped[UUID] = mapped_column(nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class DiagnosisModel(Base):
    __tablename__ = "diagnosis"
    __table_args__ = (
        UniqueConstraint("ai_decision_id", name="uq_diagnosis_ai_decision"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ai_decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_decision.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[DiagnosisStatus] = mapped_column(
        Enum(DiagnosisStatus, name="diagnosis_status"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_payload: Mapped[dict[str, JsonValue] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latest_human_decision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "human_decision.id",
            name="fk_diagnosis_latest_human_decision",
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=True,
    )

class HumanDecisionModel(Base):
    __tablename__ = "human_decision"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"),
        nullable=False,
    )
    ai_decision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai_decision.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    diagnosis_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("diagnosis.id", ondelete="RESTRICT"),
        nullable=True,
    )
    prescription_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("prescription.id", ondelete="RESTRICT"),
        nullable=True,
    )
    provider_match_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("provider_match.id", ondelete="RESTRICT"),
        nullable=True,
    )
    outcome_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("hamoon_outcome.id", ondelete="RESTRICT"),
        nullable=True,
    )
    decision_context: Mapped[HumanDecisionContext] = mapped_column(
        Enum(HumanDecisionContext, name="human_decision_context"),
        nullable=False,
    )
    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[HumanDecisionAction] = mapped_column(
        Enum(HumanDecisionAction, name="human_decision_action"),
        nullable=False,
    )
    reason_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reason_text: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    accepted_payload: Mapped[dict[str, JsonValue] | None] = mapped_column(JSON, nullable=True)
    modified_payload: Mapped[dict[str, JsonValue] | None] = mapped_column(JSON, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class DecisionTraceModel(Base):
    __tablename__ = "decision_trace"
    __table_args__ = (
        UniqueConstraint("ai_decision_id", name="uq_decision_trace_ai_decision"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trace_type: Mapped[AIDecisionType] = mapped_column(
        Enum(AIDecisionType, name="ai_decision_type"),
        nullable=False,
    )
    state_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    pgor_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    feature_package_id: Mapped[UUID] = mapped_column(
        ForeignKey("feature_package.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ai_decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_decision.id", ondelete="RESTRICT"),
        nullable=False,
    )
    human_decision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("human_decision.id", ondelete="SET NULL"),
        nullable=True,
    )
    prescription_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("prescription.id", ondelete="SET NULL"),
        nullable=True,
    )
    intervention_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("intervention.id", ondelete="SET NULL"),
        nullable=True,
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

class LearningSignalModel(Base):
    __tablename__ = "learning_signal"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    signal_type: Mapped[LearningSignalType] = mapped_column(
        Enum(LearningSignalType, name="learning_signal_type"),
        nullable=False,
    )
    ai_decision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai_decision.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    human_decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("human_decision.id", ondelete="RESTRICT"),
        nullable=False,
    )
    diagnosis_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("diagnosis.id", ondelete="RESTRICT"),
        nullable=True,
    )
    prescription_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("prescription.id", ondelete="RESTRICT"),
        nullable=True,
    )
    intervention_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("intervention.id", ondelete="RESTRICT"),
        nullable=True,
    )
    provider_match_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("provider_match.id", ondelete="RESTRICT"),
        nullable=True,
    )
    provider_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("provider.id", ondelete="RESTRICT"),
        nullable=True,
    )
    provider_result_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("provider_result.id", ondelete="RESTRICT"),
        nullable=True,
    )
    outcome_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("hamoon_outcome.id", ondelete="RESTRICT"),
        nullable=True,
    )
    signal_label: Mapped[str] = mapped_column(String(100), nullable=False)
    quality_status: Mapped[LearningSignalQuality] = mapped_column(
        Enum(LearningSignalQuality, name="learning_signal_quality"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )

class AIProviderModel(Base):
    __tablename__ = "ai_provider"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[AIProviderStatus] = mapped_column(
        Enum(AIProviderStatus, name="ai_provider_status"),
        nullable=False,
    )
    adapter_type: Mapped[str] = mapped_column(String(150), nullable=False)
    data_processing_policy_ref: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

class AIModelModel(Base):
    __tablename__ = "ai_model"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    model_key: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    provider_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_provider.id", ondelete="RESTRICT"),
        nullable=False,
    )
    purpose: Mapped[str] = mapped_column(String(250), nullable=False)

class AIModelVersionModel(Base):
    __tablename__ = "ai_model_version"
    __table_args__ = (
        UniqueConstraint(
            "ai_model_id",
            "version",
            name="uq_ai_model_version_model_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ai_model_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_model.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    concrete_model_id: Mapped[str] = mapped_column(String(250), nullable=False)
    status: Mapped[AIModelVersionStatus] = mapped_column(
        Enum(AIModelVersionStatus, name="ai_model_version_status"),
        nullable=False,
    )
    limitations: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deployed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

class PromptPolicyModel(Base):
    __tablename__ = "prompt_policy"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    purpose: Mapped[str] = mapped_column(String(150), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)

class PromptPolicyVersionModel(Base):
    __tablename__ = "prompt_policy_version"
    __table_args__ = (
        UniqueConstraint(
            "prompt_policy_id",
            "version",
            name="uq_prompt_policy_version_policy_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    prompt_policy_id: Mapped[UUID] = mapped_column(
        ForeignKey("prompt_policy.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    instructions: Mapped[str] = mapped_column(String(8000), nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    guardrail_version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[PromptPolicyVersionStatus] = mapped_column(
        Enum(PromptPolicyVersionStatus, name="prompt_policy_version_status"),
        nullable=False,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

class EvaluationRunModel(Base):
    __tablename__ = "evaluation_run"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    task_class: Mapped[AITaskClass] = mapped_column(
        Enum(AITaskClass, name="ai_task_class"),
        nullable=False,
    )
    model_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_model_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    prompt_policy_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("prompt_policy_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    evaluation_policy_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    status: Mapped[EvaluationStatus] = mapped_column(
        Enum(EvaluationStatus, name="ai_evaluation_status"),
        nullable=False,
    )
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    summary_metrics: Mapped[dict[str, JsonValue]] = mapped_column(JSON, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

class ModelRoutingPolicyModel(Base):
    __tablename__ = "model_routing_policy"
    __table_args__ = (
        UniqueConstraint(
            "task_class",
            "version",
            name="uq_model_routing_policy_task_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    task_class: Mapped[AITaskClass] = mapped_column(
        Enum(AITaskClass, name="ai_task_class"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    model_alias: Mapped[str] = mapped_column(String(150), nullable=False)
    model_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_model_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    prompt_policy_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("prompt_policy_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    evaluation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation_run.id", ondelete="RESTRICT"),
        nullable=False,
    )
    structured_output_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    status: Mapped[RoutingPolicyStatus] = mapped_column(
        Enum(RoutingPolicyStatus, name="model_routing_policy_status"),
        nullable=False,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
